"""Direct-audio verdict routing: STT is a PARALLEL helper.

* audio_tools defaults to none (Gemma hears the audio without tools)
* classify_text_path() is a pure predicate (direct | text | greeting)
* ungated (conversation window) answers are buffered until the STT verdict
  or the timeout; a finished direct answer is never delayed by the timer
* text/greeting verdicts cancel the Gemma request and run the normal text path
* a bare wake word never reaches Gemma

All fakes, no network.
"""

import queue
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from core.audio_turn_routing import (DIRECT, GREETING, TEXT, is_wake_only,
                                     keyword_text_path_reason)
from core.conversation_router import classify_text_path
from core.direct_audio import DirectAudioService
from core.events import Event, EventType, PipelineState
from core.llm_router import LLMRouter
from core.pipeline import Coordinator


class Cfg:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


AUDIO = np.zeros(1600, dtype=np.float32)


class FakeLLM:
    tool_calling = True

    def __init__(self, tokens=("Hallo", " Welt"), hold=None):
        self.tokens = list(tokens)
        self.hold = hold
        self.cancelled = 0
        self.calls = []
        self.started = threading.Event()
        self.encode_audio_wav_b64 = LLMRouter.encode_audio_wav_b64

    def probe_role(self, role=None, ttl=None, timeout=1.0):
        return "READY"

    def stream(self, **kw):
        self.calls.append(("stream", kw))
        self.started.set()
        yield from self.tokens
        if self.hold is not None:
            self.hold.wait(2.0)

    def stream_with_tools(self, **kw):
        self.calls.append(("stream_with_tools", kw))
        self.started.set()
        yield from self.tokens

    def cancel_active_stream(self, handle=None):
        self.cancelled += 1
        if self.hold is not None:
            self.hold.set()


def cfg(**extra):
    values = {"llm.primary.audio_direct": True, "stt.wake_compat": True,
              "llm.primary.ready_wait_s": 1, "llm.primary.stt_verdict_timeout_s": 3.0}
    values.update(extra)
    return Cfg(**values)


# ---------------------------------------------------------------------------
# pure predicate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["Aura", "Aura.", "aura!", "Aura?", "Aura。", " Aura, "])
def test_is_wake_only_true_for_bare_wake_word(text):
    assert is_wake_only(text, "aura")


@pytest.mark.parametrize("text", ["", "Aura wie spät ist es", "Wetter", "danke Aura schön"])
def test_is_wake_only_false_otherwise(text):
    assert not is_wake_only(text, "aura")


@pytest.mark.parametrize("text,path", [
    ("wie spät ist es", TEXT),
    ("Wetter in Stuttgart", TEXT),
    ("erinnere mich morgen an den Zahnarzt", TEXT),
    ("öffne den Browser", TEXT),
    ("Erzähl mir einen Witz", DIRECT),
    ("Antworte nur auf Deutsch", DIRECT),
    ("und morgen?", DIRECT),
    ("Aura", GREETING),
    ("Aura.", GREETING),
])
def test_classify_text_path(text, path):
    assert classify_text_path(text)[0] == path


def test_classify_strips_wake_and_reports_reason():
    action, command, reason = classify_text_path("Aura, wie spät ist es?")
    assert action == TEXT and command == "wie spät ist es" and reason == "keyword:time"
    assert classify_text_path("Aura")[1] == "jarvis_only"


def test_classify_is_pure_and_never_routes():
    class Router:
        def route(self, *a, **k):
            raise AssertionError("route() must never be called by the predicate")

        def __getattr__(self, name):
            raise AssertionError(f"predicate touched router state: {name}")

        def text_path_reason(self, command, in_conversation=False):
            return "skill:demo"

    assert classify_text_path("mach was", router=Router())[:3] == (TEXT, "mach was", "skill:demo")
    assert keyword_text_path_reason("Erzähl einen Witz") is None


# ---------------------------------------------------------------------------
# audio_tools default: none
# ---------------------------------------------------------------------------

def make_ctx_coordinator(**values):
    coord = Coordinator.__new__(Coordinator)
    coord.config = cfg(**values)
    coord.conversation = SimpleNamespace(current_user="christopher",
                                         format_history_for_llm=lambda **k: "USER: hi")
    coord.logger = SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None,
                                   warning=lambda *a, **k: None)
    return coord


def test_direct_audio_context_has_no_tools_by_default():
    coord = make_ctx_coordinator()
    ctx = coord._direct_audio_context(SimpleNamespace(placeholder="[x]", in_conversation=True))
    assert ctx["tools"] is None and ctx["history"] == "USER: hi"
    ctx = coord._direct_audio_context(SimpleNamespace(placeholder="[x]", in_conversation=True))
    assert coord._direct_route_result(SimpleNamespace(context=ctx)).use_tools is None


@pytest.mark.parametrize("mode", ["none", "", None])
def test_audio_tools_none_variants_send_no_tools(mode):
    coord = make_ctx_coordinator(**{"llm.primary.audio_tools": mode})
    assert coord._direct_audio_context(SimpleNamespace(placeholder="x", in_conversation=False))["tools"] is None


@pytest.mark.parametrize("mode", ["always", "all"])
def test_audio_tools_opt_in(mode):
    coord = make_ctx_coordinator(**{"llm.primary.audio_tools": mode})
    tools = coord._direct_audio_context(SimpleNamespace(placeholder="x", in_conversation=False))["tools"]
    assert tools and all(t["function"]["name"] != "delegate_to_expert" for t in tools)


def test_direct_request_payload_carries_no_tools():
    llm = FakeLLM()
    svc = DirectAudioService(llm, cfg(**{"llm.primary.stt_verdict_timeout_s": 0}),
                             context_provider=lambda at: make_ctx_coordinator()._direct_audio_context(at))
    at = svc.start_turn(AUDIO, in_conversation=True)
    assert list(at.turn.stream()) == ["Hallo", " Welt"]
    kind, kw = llm.calls[0]
    assert kind == "stream" and "tools" not in kw and kw["role"] == "primary"


# ---------------------------------------------------------------------------
# verdict hold in DirectAudioService
# ---------------------------------------------------------------------------

def collect(at, out, done):
    for item in at.turn.stream():
        out.append(item)
    done.set()


def test_ungated_turn_is_buffered_until_verdict_then_released():
    llm = FakeLLM()
    svc = DirectAudioService(llm, cfg())
    at = svc.start_turn(AUDIO, in_conversation=True)
    assert at.hold_for_verdict and not at.gate_required
    out, done = [], threading.Event()
    threading.Thread(target=collect, args=(at, out, done), daemon=True).start()
    assert llm.started.wait(1.0)
    time.sleep(0.15)
    assert out == [] and not done.is_set()                 # buffered, nothing visible yet

    assert svc.set_verdict(at, "direct", "", "chat") is True

    assert done.wait(1.0) and out == ["Hallo", " Welt"]
    assert svc.set_verdict(at, "text", "x") is False        # first verdict wins
    assert at.verdict_event.is_set()


def test_early_verdict_is_not_delayed_by_timer():
    svc = DirectAudioService(FakeLLM(), cfg(**{"llm.primary.stt_verdict_timeout_s": 30}))
    at = svc.start_turn(AUDIO, in_conversation=True)
    out, done = [], threading.Event()
    threading.Thread(target=collect, args=(at, out, done), daemon=True).start()
    t0 = time.monotonic()
    time.sleep(0.05)
    svc.set_verdict(at, "direct")
    assert done.wait(1.0)
    assert time.monotonic() - t0 < 2.0
    assert at._verdict_timer is not None and not at._verdict_timer.is_alive()   # timer cancelled


def test_timeout_releases_direct_answer():
    svc = DirectAudioService(FakeLLM(), cfg(**{"llm.primary.stt_verdict_timeout_s": 0.2}))
    at = svc.start_turn(AUDIO, in_conversation=True)
    out, done = [], threading.Event()
    threading.Thread(target=collect, args=(at, out, done), daemon=True).start()
    assert done.wait(2.0) and out == ["Hallo", " Welt"]
    assert at.verdict_action == "direct" and at.verdict_reason == "stt_timeout"


@pytest.mark.parametrize("action", ["text", "greeting"])
def test_text_or_greeting_verdict_cancels_request_and_supersedes(action):
    llm = FakeLLM(hold=threading.Event())
    svc = DirectAudioService(llm, cfg())
    at = svc.start_turn(AUDIO, in_conversation=True)
    assert llm.started.wait(1.0)
    assert svc.set_verdict(at, action, "wie spät ist es", "keyword:time")
    assert at.superseded and at.turn.is_rejected and llm.cancelled == 1
    assert at.turn.buffered_items == []
    assert list(at.turn.stream()) == []


def test_reject_verdict_cancels_without_superseding():
    llm = FakeLLM(hold=threading.Event())
    svc = DirectAudioService(llm, cfg())
    at = svc.start_turn(AUDIO, in_conversation=True)
    svc.set_verdict(at, "reject", "", "noise")
    assert at.turn.is_rejected and not at.superseded and llm.cancelled == 1


def test_timer_is_cancelled_on_pop_and_discard():
    svc = DirectAudioService(FakeLLM(), cfg(**{"llm.primary.stt_verdict_timeout_s": 30}))
    a = svc.start_turn(AUDIO, in_conversation=True)
    b = svc.start_turn(AUDIO, in_conversation=True)
    svc.pop(a.turn_id)
    assert a._verdict_timer.finished.is_set()
    svc.discard_all()
    assert b._verdict_timer.finished.is_set()


def test_active_popped_turn_is_tracked_until_finish():
    svc = DirectAudioService(FakeLLM(), cfg(**{"llm.primary.stt_verdict_timeout_s": 0}))
    at = svc.start_turn(AUDIO, in_conversation=True)
    assert svc.pop(at.turn_id, active=True) is at
    assert svc.get(at.turn_id) is None and svc.active_turns() == [at]
    svc.finish(at)
    assert svc.active_turns() == []


# ---------------------------------------------------------------------------
# Coordinator: verdict decision + command flow
# ---------------------------------------------------------------------------

def make_coordinator(llm, **values):
    coord = Coordinator.__new__(Coordinator)
    coord.config = cfg(**values)
    coord.llm = llm
    coord.wake_word = "aura"
    coord.event_queue = queue.Queue()
    coord.logger = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None,
                                   debug=lambda *a, **k: None, error=lambda *a, **k: None)
    coord.direct_audio = DirectAudioService(
        llm, coord.config, context_provider=lambda at: coord._direct_audio_context(at))
    coord.conversation = SimpleNamespace(current_user="christopher", session_history=[],
                                         format_history_for_llm=lambda **k: "",
                                         add_message=lambda *a, **k: None,
                                         request_follow_up=None,
                                         get_conversation_stats=lambda: {
                                             "session_user_messages": 0,
                                             "session_assistant_messages": 0})
    coord.listener = SimpleNamespace(
        conversation_window_active=True, _capture_generation=1, _extended_duration=12.0,
        pause_listening=lambda: None, resume_listening=lambda: None,
        open_conversation_window=lambda d: None, _speaking_event=threading.Event())
    coord._valid_short_replies = {"ja", "nein", "ok"}
    coord.router = SimpleNamespace(
        route=None, text_path_reason=lambda c, i=False: keyword_text_path_reason(c))
    coord._turn_cancelled = threading.Event()
    coord._stop_only_interrupt = False
    coord._active_response_text = ""
    coord._pending_expert = None
    coord._llm_responded = False
    coord._active_audio_pipeline = None
    coord._retired_audio_pipelines = []
    coord._streaming_active = False
    coord.state = PipelineState.IDLE
    coord.stats = {"commands_processed": 0}
    coord.memory_manager = None
    coord.accumulator = None
    coord.tts = SimpleNamespace(_spoke=False)
    coord._last_speaker_confidence = 0.9
    coord._rapid_switch_count = 0
    coord._last_command_start_ts = coord._last_command_end_ts = coord._last_idle_ts = 0.0
    coord._play_beep = lambda: None
    coord._classify_ack = lambda *a, **k: ("x", True)
    coord._record_metrics = lambda *a, **k: None
    def speak(text):
        coord.spoken.append(text)
        coord.tts._spoke = True

    coord._speak_and_wait = speak
    coord._manage_conversation_window = lambda *a, **k: None
    coord.conv_state = SimpleNamespace(jarvis_asked_question=False, update=lambda **k: None)
    coord.llm.strip_metric = lambda r, c: r
    coord.llm.strip_filler = lambda r: r
    coord.spoken = []
    coord.streams = []
    coord.routes = []
    coord.greetings = []

    def fake_route(command, in_conversation=False):
        coord.routes.append((command, in_conversation))
        from core.conversation_router import RouteResult
        return RouteResult(handled=True, text="Es ist zehn Uhr.", intent="skill")

    coord.router.route = fake_route

    def fake_stream(command, history, **kw):
        coord.streams.append(kw)
        src = kw.get("token_source_override")
        return "".join(t for t in src if isinstance(t, str)) if src is not None else ""

    coord._stream_llm_response = fake_stream
    coord._handle_minimal_greeting = lambda command, in_conv: coord.greetings.append(command)
    return coord


def start(coord, in_conversation=True):
    coord.listener.conversation_window_active = in_conversation
    at = coord.direct_audio.start_turn(AUDIO, generation=1, in_conversation=in_conversation)
    return at


def command_event(at):
    return Event(EventType.COMMAND_DETECTED, data={"direct_audio_turn": at.turn_id}, source="t")


@pytest.mark.parametrize("text,action", [
    ("(Husten)", "reject"),
    ("[Musik]", "reject"),
    ("aaaaaaaaaaaaaaaa", "reject"),
    ("", "reject"),
    ("hm", "reject"),
    ("wie spät ist es", "text"),
    ("Aura", "greeting"),
    ("erzähl mir einen Witz", "direct"),
])
def test_ungated_decision_from_transcript(text, action):
    coord = make_coordinator(FakeLLM())
    at = start(coord)
    assert coord._direct_turn_decision(at, text)[0] == action


def test_resolve_ungated_applies_verdicts_and_sets_asr_hint():
    coord = make_coordinator(FakeLLM(hold=threading.Event()))
    at = start(coord)
    coord.resolve_ungated_audio_turn(at, "erzähl mir einen Witz")
    assert at.verdict_action == "direct" and at.asr_hint == "erzähl mir einen Witz"

    at2 = start(coord)
    coord.resolve_ungated_audio_turn(at2, None, "blank")
    assert at2.verdict_action == "reject" and at2.turn.is_rejected

    at3 = start(coord)
    coord.resolve_ungated_audio_turn(at3, None, "stt_error")     # STT is only a helper
    assert at3.verdict_action == "direct" and not at3.turn.is_rejected


def test_command_direct_verdict_streams_gemma_without_tools():
    llm = FakeLLM()
    coord = make_coordinator(llm)
    at = start(coord)
    coord.resolve_ungated_audio_turn(at, "erzähl mir einen Witz")

    coord._handle_command(command_event(at))

    assert coord.routes == [] and len(coord.streams) == 1
    assert coord.streams[0]["use_tools"] is None
    assert coord.streams[0]["token_source_override"] is not None
    assert coord.direct_audio.active_turns() == []            # finished/untracked


def test_command_text_verdict_cancels_gemma_and_runs_text_path():
    llm = FakeLLM(hold=threading.Event())
    coord = make_coordinator(llm)
    at = start(coord)
    assert llm.started.wait(1.0)
    coord.resolve_ungated_audio_turn(at, "Aura, wie spät ist es?")

    coord._handle_command(command_event(at))

    assert llm.cancelled >= 1 and coord.streams == []
    assert coord.routes == [("wie spät ist es", True)]
    assert coord.spoken == ["Es ist zehn Uhr."]


def test_command_bare_wake_goes_to_minimal_greeting_not_gemma():
    llm = FakeLLM(hold=threading.Event())
    coord = make_coordinator(llm)
    at = start(coord)
    coord.resolve_ungated_audio_turn(at, "Aura.")

    coord._handle_command(command_event(at))

    assert coord.greetings == ["jarvis_only"]
    assert coord.streams == [] and coord.routes == [] and llm.cancelled >= 1


def test_command_noise_verdict_gives_no_answer_and_returns_to_idle():
    llm = FakeLLM(hold=threading.Event())
    coord = make_coordinator(llm)
    at = start(coord)
    coord.resolve_ungated_audio_turn(at, "(Husten)")

    coord._handle_command(command_event(at))

    assert coord.streams == [] and coord.routes == [] and coord.spoken == []
    assert coord.state is PipelineState.IDLE


def test_verdict_arriving_from_stt_thread_while_command_waits():
    llm = FakeLLM()
    coord = make_coordinator(llm)
    at = start(coord)
    threading.Timer(0.1, coord.resolve_ungated_audio_turn,
                    args=(at, "erzähl mir einen Witz")).start()
    t0 = time.monotonic()

    coord._handle_command(command_event(at))

    assert len(coord.streams) == 1 and time.monotonic() - t0 < 2.0


def test_no_verdict_times_out_to_direct_answer():
    coord = make_coordinator(FakeLLM(), **{"llm.primary.stt_verdict_timeout_s": 0.2})
    at = start(coord)
    coord._handle_command(command_event(at))
    assert len(coord.streams) == 1 and coord.routes == []


def test_pending_expert_is_reset_at_command_start():
    coord = make_coordinator(FakeLLM(), **{"llm.primary.stt_verdict_timeout_s": 0})
    coord._pending_expert = object()
    at = start(coord)
    coord._handle_command(command_event(at))
    assert coord._pending_expert is None


def test_finish_cancelled_turn_clears_pending_expert():
    coord = make_coordinator(FakeLLM())
    coord._pending_expert = object()
    coord._finish_cancelled_turn()
    assert coord._pending_expert is None


# ---------------------------------------------------------------------------
# gated (wake word) turns
# ---------------------------------------------------------------------------

def drain_events(coord):
    events = []
    while not coord.event_queue.empty():
        events.append(coord.event_queue.get())
    return events


def test_gated_bare_wake_never_reaches_gemma():
    llm = FakeLLM(hold=threading.Event())
    coord = make_coordinator(llm)
    coord._is_ambient_wake_word = lambda t, m: False
    at = start(coord, in_conversation=False)
    assert at.gate_required and llm.started.wait(1.0)

    assert coord._resolve_direct_turn_from_transcript(at.turn_id, "Aura.") is True

    events = drain_events(coord)
    assert len(events) == 1 and events[0].type is EventType.COMMAND_DETECTED
    assert events[0].data == "jarvis_only"
    assert at.turn.is_rejected and llm.cancelled == 1
    assert coord.direct_audio.get(at.turn_id) is None


def test_gated_tool_sentence_is_diverted_with_stripped_command():
    llm = FakeLLM(hold=threading.Event())
    coord = make_coordinator(llm)
    coord._is_ambient_wake_word = lambda t, m: False
    at = start(coord, in_conversation=False)
    assert llm.started.wait(1.0)

    coord._resolve_direct_turn_from_transcript(at.turn_id, "Aura, Wetter in Stuttgart")

    events = drain_events(coord)
    assert [e.data for e in events] == ["wetter in stuttgart"]
    assert at.turn.is_rejected and at.turn.buffered_items == []


def test_gated_chat_sentence_confirms_gemma_once():
    llm = FakeLLM()
    coord = make_coordinator(llm)
    coord._is_ambient_wake_word = lambda t, m: False
    at = start(coord, in_conversation=False)
    coord._resolve_direct_turn_from_transcript(at.turn_id, "Aura erzähl mir einen Witz")
    events = drain_events(coord)
    assert [e.data for e in events] == [{"direct_audio_turn": at.turn_id}]
    assert at.turn.is_confirmed and llm.cancelled == 0


# ---------------------------------------------------------------------------
# speaker context after identification
# ---------------------------------------------------------------------------

def test_context_is_rebuilt_when_speaker_turns_out_to_be_guest():
    llm = FakeLLM(hold=threading.Event())
    coord = make_coordinator(llm, **{"llm.primary.stt_verdict_timeout_s": 0})
    coord.conversation.format_history_for_llm = lambda **k: "USER: geheimer Besitzer-Verlauf"
    at = start(coord)                                   # started with the previous speaker (owner)
    assert at.context["guest_mode"] is False and "geheimer" in at.context["history"]
    assert llm.started.wait(1.0)
    at.speaker_id, at.speaker_confidence, at.speaker_resolved = None, 0.0, True

    def apply(speaker_id, confidence):
        coord.conversation.current_user = "__guest__" if speaker_id is None else speaker_id

    coord._apply_speaker_context = apply
    coord.direct_audio.pop(at.turn_id, active=True)
    coord._finalize_direct_context(at)

    assert at.context["guest_mode"] is True and at.context["history"] == ""
    assert llm.cancelled == 1                                     # old request (owner history) cancelled
    time.sleep(0.2)
    guest_call = llm.calls[-1][1]
    assert guest_call["guest_mode"] is True and guest_call["conversation_history"] == ""
