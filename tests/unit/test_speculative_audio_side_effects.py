"""Wake speculation guardrail: a speculative Gemma turn is side-effect-free
until the wake word is confirmed.

Before confirmation: zero tool calls, zero memory writes, ConversationState
unchanged, no persisted history, no TTS, no UI publish. No wake -> the active
stream is cancelled and the buffer discarded. Wake confirmed -> effects are
released exactly once. Inside a conversation window there is no gate.
"""

import queue
import threading
import time
from types import SimpleNamespace

import numpy as np

from core.direct_audio import DirectAudioService
from core.events import EventType
from core.llm_router import LLMRouter, ToolCallRequest
from core.pipeline import Coordinator
from core.speculative_turn import CONFIRMED, PENDING, REJECTED, SpeculativeTurn


class Effects:
    """Everything a turn could do to the outside world."""

    def __init__(self):
        self.tool_calls = []
        self.memory_writes = []
        self.state_mutations = []
        self.history = []
        self.tts = []
        self.ui = []

    def total(self):
        return sum(len(x) for x in (self.tool_calls, self.memory_writes, self.state_mutations,
                                     self.history, self.tts, self.ui))


def consume(turn, fx, done=None):
    """Mimics the coordinator side: every effect is driven by a consumed item."""
    for item in turn.stream():
        if isinstance(item, ToolCallRequest):
            fx.tool_calls.append(item.name)
            fx.memory_writes.append("tool-result")
        else:
            fx.state_mutations.append("conv_state")
            fx.history.append(item)
            fx.tts.append(item)
            fx.ui.append(item)
    if done:
        done.set()


class GatedSource:
    """LLM stream stand-in: emits tokens + a tool call, then waits to be closed."""

    def __init__(self, items, hold=None):
        self.items = list(items)
        self.hold = hold
        self.produced = threading.Event()
        self.closed = threading.Event()

    def __iter__(self):
        try:
            for item in self.items:
                yield item
            self.produced.set()
            if self.hold is not None:
                self.hold.wait(2.0)
        finally:
            self.closed.set()


ITEMS = ["Guten", " Tag", ToolCallRequest(name="get_weather", arguments={"city": "Berlin"}, call_id="1")]


def wait_for(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_no_effects_before_wake_confirmed():
    fx = Effects()
    cancels = []
    src = GatedSource(ITEMS)
    turn = SpeculativeTurn(gate_required=True, cancel_cb=lambda: cancels.append(1))
    turn.begin(src)
    t = threading.Thread(target=consume, args=(turn, fx), daemon=True)
    t.start()

    assert src.produced.wait(1.0)                      # request ran to completion...
    assert wait_for(lambda: len(turn.buffered_items) == 3)
    time.sleep(0.1)

    assert turn.state == PENDING
    assert turn.buffered_tokens == ["Guten", " Tag"]   # ...but tokens are only buffered
    assert fx.tool_calls == [] and fx.memory_writes == []
    assert fx.state_mutations == [] and fx.history == []
    assert fx.tts == [] and fx.ui == []
    assert fx.total() == 0
    assert not turn.effects_allowed
    assert cancels == []
    turn.reject()
    t.join(2.0)


def test_no_wake_cancels_stream_and_discards_buffer():
    fx = Effects()
    cancels = []
    hold = threading.Event()
    src = GatedSource(["a", "b"], hold=hold)
    turn = SpeculativeTurn(gate_required=True, cancel_cb=lambda: (cancels.append(1), hold.set()))
    turn.begin(src)
    t = threading.Thread(target=consume, args=(turn, fx), daemon=True)
    t.start()
    assert wait_for(lambda: len(turn.buffered_items) == 2)

    assert turn.reject() is True

    assert cancels == [1]                               # cancel_active_stream called once
    assert turn.state == REJECTED
    assert turn.buffered_items == [] and turn.buffered_tokens == []
    assert src.closed.wait(2.0)                         # producer stopped
    t.join(2.0)
    assert fx.total() == 0                              # nothing ever leaked
    # idempotent + a rejected turn can never be confirmed afterwards
    assert turn.reject() is False and cancels == [1]
    assert turn.confirm_wake() is False
    assert fx.total() == 0


def test_wake_confirmed_releases_effects_exactly_once():
    fx = Effects()
    released = []
    src = GatedSource(ITEMS)
    turn = SpeculativeTurn(gate_required=True, on_release=lambda buf: released.append(list(buf)))
    turn.begin(src)
    done = threading.Event()
    threading.Thread(target=consume, args=(turn, fx, done), daemon=True).start()
    assert wait_for(lambda: len(turn.buffered_items) == 3)
    assert fx.total() == 0 and released == []

    assert turn.confirm_wake() is True
    assert turn.confirm_wake() is False                 # second confirm is a no-op
    assert done.wait(2.0)

    assert turn.state == CONFIRMED and turn.release_count == 1
    assert len(released) == 1                            # release callback exactly once
    assert fx.history == ["Guten", " Tag"]               # buffered tokens released in order, once
    assert fx.tts == ["Guten", " Tag"] and fx.ui == ["Guten", " Tag"]
    assert fx.tool_calls == ["get_weather"]              # the tool runs once, only now
    assert turn.reject() is False                        # released turns cannot be rejected


def test_live_tokens_after_confirm_stream_through():
    hold = threading.Event()
    src = GatedSource(["eins"], hold=hold)
    turn = SpeculativeTurn(gate_required=True)
    turn.begin(src)
    out = []
    done = threading.Event()

    def run():
        out.extend(turn.stream())
        done.set()

    threading.Thread(target=run, daemon=True).start()
    turn.confirm_wake()
    assert wait_for(lambda: out == ["eins"])
    hold.set()
    assert done.wait(2.0)


def test_conversation_window_has_no_gate():
    fx = Effects()
    released = []
    src = GatedSource(ITEMS)
    turn = SpeculativeTurn(gate_required=False, on_release=lambda buf: released.append(1))
    turn.begin(src)
    done = threading.Event()
    threading.Thread(target=consume, args=(turn, fx, done), daemon=True).start()

    assert done.wait(2.0)                               # no confirm_wake needed

    assert turn.state == CONFIRMED and len(released) == 1
    assert fx.tts == ["Guten", " Tag"] and fx.tool_calls == ["get_weather"]


def test_decision_timeout_rejects_without_wake_evidence():
    cancels = []
    turn = SpeculativeTurn(gate_required=True, cancel_cb=lambda: cancels.append(1))
    turn.begin(GatedSource(["x"]))
    assert list(turn.stream(decision_timeout=0.1)) == []
    assert turn.state == REJECTED and cancels == [1]


# ---------------------------------------------------------------------------
# Coordinator wiring: transcript wake result drives confirm/reject
# ---------------------------------------------------------------------------

class Cfg:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class FakeLLM:
    tool_calling = False

    def __init__(self):
        self.cancelled = 0
        self.hold = threading.Event()
        self.started = threading.Event()
        self.encode_audio_wav_b64 = LLMRouter.encode_audio_wav_b64

    def probe_role(self, role=None, ttl=None, timeout=1.0):
        return "READY"

    def stream(self, **kw):
        self.started.set()
        yield "Hallo"
        self.hold.wait(2.0)

    def cancel_active_stream(self):
        self.cancelled += 1
        self.hold.set()


def make_coordinator(llm, wake_compat=True, verdict_timeout=0):
    cfg = Cfg({"llm.primary.audio_direct": True, "stt.wake_compat": wake_compat,
               "llm.primary.ready_wait_s": 1,
               "llm.primary.stt_verdict_timeout_s": verdict_timeout})
    coord = Coordinator.__new__(Coordinator)
    coord.direct_audio = DirectAudioService(llm, cfg)
    coord.wake_word = "aura"
    coord.event_queue = queue.Queue()
    coord.logger = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None,
                                   debug=lambda *a, **k: None)
    coord._is_ambient_wake_word = lambda text, matched: False
    return coord


AUDIO = np.zeros(1600, dtype=np.float32)


def test_transcript_without_wake_rejects_turn_and_cancels_stream():
    llm = FakeLLM()
    coord = make_coordinator(llm)
    at = coord.direct_audio.start_turn(AUDIO, in_conversation=False)
    assert at.gate_required and llm.started.wait(1.0)

    consumed = coord._resolve_direct_turn_from_transcript(at.turn_id, "wie spät ist es")

    assert consumed is True
    assert at.turn.is_rejected and llm.cancelled == 1
    assert at.turn.buffered_items == []
    assert coord.direct_audio.get(at.turn_id) is None
    assert coord.event_queue.empty()                    # no COMMAND_DETECTED -> no effects


def test_transcript_with_wake_confirms_once_and_emits_single_command():
    llm = FakeLLM()
    coord = make_coordinator(llm)
    at = coord.direct_audio.start_turn(AUDIO, in_conversation=False)
    assert llm.started.wait(1.0)
    assert coord.event_queue.empty()                    # nothing dispatched before wake

    coord._resolve_direct_turn_from_transcript(at.turn_id, "aura erzähl mir einen Witz")
    coord._resolve_direct_turn_from_transcript(at.turn_id, "aura erzähl mir einen Witz")  # duplicate STT event

    events = []
    while not coord.event_queue.empty():
        events.append(coord.event_queue.get())
    assert len(events) == 1
    assert events[0].type == EventType.COMMAND_DETECTED
    assert events[0].data == {"direct_audio_turn": at.turn_id}
    assert at.turn.state == CONFIRMED and at.turn.release_count == 1
    assert at.asr_hint == "aura erzähl mir einen Witz"  # metadata only
    assert llm.cancelled == 0
    llm.hold.set()


def test_conversation_window_turn_is_not_gated_and_transcript_is_metadata():
    llm = FakeLLM()
    coord = make_coordinator(llm)
    at = coord.direct_audio.start_turn(AUDIO, in_conversation=True)
    assert not at.gate_required and at.turn.effects_allowed

    consumed = coord._resolve_direct_turn_from_transcript(at.turn_id, "und morgen?")

    assert consumed is True
    assert coord.event_queue.empty()                    # STT worker already dispatched the turn
    assert at.asr_hint == "und morgen?" and not at.turn.is_rejected
    llm.hold.set()


def test_wake_compat_disabled_removes_gate():
    llm = FakeLLM()
    coord = make_coordinator(llm, wake_compat=False)
    at = coord.direct_audio.start_turn(AUDIO, in_conversation=False)
    assert not at.gate_required
    llm.hold.set()


def test_reject_audio_turn_ignores_ungated_turns():
    llm = FakeLLM()
    coord = make_coordinator(llm)
    at = coord.direct_audio.start_turn(AUDIO, in_conversation=True)
    assert coord.reject_audio_turn(at.turn_id, "blank") is False
    assert not at.turn.is_rejected
    llm.hold.set()


def test_producer_error_is_logged_by_type_only(caplog):
    import logging

    def broken():
        yield "geheimer Inhalt"
        raise ValueError("geheimer Inhalt im Fehler")

    turn = SpeculativeTurn(gate_required=False)
    with caplog.at_level(logging.WARNING, logger="jarvis.speculative_turn"):
        turn.begin(broken())
        turn.join(2.0)
    assert isinstance(turn.error, ValueError)
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "ValueError" in text and "geheimer" not in text
