"""Privacy gate vs. the direct-audio voice path (audit finding 1).

Audio that is queued or being transcribed while privacy is entered must not
start a model request, must not fall into the legacy text path and must cancel
running direct-audio turns. All fakes, no network.
"""

import queue
import threading
import time
from types import SimpleNamespace

import numpy as np

from core.direct_audio import DirectAudioService
from core.events import Event, EventType, PipelineState
from core.llm_router import LLMRouter
from core.pipeline import Coordinator, STTWorker

AUDIO = np.ones(16000, dtype=np.float32)


class Cfg:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class FakeGate:
    def __init__(self):
        self.allowed = True
        self._epoch = "e1"

    def allow(self, capability):
        return self.allowed

    def epoch(self):
        return self._epoch

    def is_current_epoch(self, epoch):
        return epoch == self._epoch

    def enter(self):
        self.allowed = False
        self._epoch = "e2"


class FakeLLM:
    tool_calling = False

    def __init__(self):
        self.cancelled = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.encode_audio_wav_b64 = LLMRouter.encode_audio_wav_b64

    def probe_role(self, role=None, ttl=None, timeout=1.0):
        return "READY"

    def stream(self, **kw):
        self.started.set()
        yield "Hallo"
        self.release.wait(2.0)

    def cancel_active_stream(self, handle=None):
        self.cancelled += 1
        self.release.set()


class FakeSTT:
    def __init__(self, text="erzähl mir einen Witz", on_transcribe=None):
        self.text = text
        self.calls = 0
        self.on_transcribe = on_transcribe

    def transcribe(self, audio, sr, **kw):
        self.calls += 1
        if self.on_transcribe:
            self.on_transcribe()
        return self.text


def make_worker(gate, stt, audio_turn_factory=None):
    events = queue.Queue()
    audio_queue = queue.Queue()
    worker = STTWorker(stt, events, audio_queue, config=None, listener=None)
    worker._privacy_gate = gate
    worker.started = []
    worker.cancelled = []

    def on_audio_turn(audio, generation):
        worker.started.append(1)
        return audio_turn_factory() if audio_turn_factory else None

    worker.on_audio_turn = on_audio_turn
    worker.on_audio_turn_cancel = lambda tid, reason: worker.cancelled.append((tid, reason))
    return worker, events, audio_queue


def run(worker, audio_queue):
    audio_queue.put({"audio": AUDIO, "capture_generation": None, "during_tts": False})
    audio_queue.put(None)
    worker.start()
    worker.join(5)


def test_stt_worker_drops_queued_audio_when_privacy_active():
    gate = FakeGate()
    gate.enter()
    stt = FakeSTT()
    worker, events, audio_queue = make_worker(gate, stt)
    run(worker, audio_queue)
    assert worker.started == [] and stt.calls == 0 and events.empty()


def test_privacy_entered_during_transcribe_cancels_turn_and_emits_nothing():
    gate = FakeGate()
    llm = FakeLLM()
    svc = DirectAudioService(llm, Cfg(**{"llm.primary.audio_direct": True,
                                        "stt.wake_compat": False,
                                        "llm.primary.stt_verdict_timeout_s": 0}))
    holder = {}

    def factory():
        holder["at"] = svc.start_turn(AUDIO, in_conversation=True)
        return holder["at"]

    stt = FakeSTT(on_transcribe=gate.enter)
    worker, events, audio_queue = make_worker(gate, stt, factory)
    run(worker, audio_queue)

    at = holder["at"]
    assert worker.cancelled == [(at.turn_id, "privacy")]
    assert events.qsize() == 1                                  # only the COMMAND_DETECTED of the ungated turn
    assert events.get_nowait().type is EventType.COMMAND_DETECTED
    assert stt.calls == 1                                       # no TRANSCRIPTION_READY


def test_privacy_during_transcribe_without_turn_hook_falls_back_to_reject():
    gate = FakeGate()

    class Turn:
        turn_id = "a9"
        gate_required = True
        hold_for_verdict = False

    rejected = []
    worker, events, audio_queue = make_worker(gate, FakeSTT(on_transcribe=gate.enter),
                                              lambda: Turn())
    worker.on_audio_turn_cancel = None
    worker.on_audio_turn_reject = lambda tid, reason: rejected.append((tid, reason))
    run(worker, audio_queue)
    assert rejected == [("a9", "privacy")] and events.empty()


def make_coordinator():
    llm = FakeLLM()
    coord = Coordinator.__new__(Coordinator)
    coord.config = Cfg(**{"llm.primary.audio_direct": True, "stt.wake_compat": True})
    coord.llm = llm
    coord.wake_word = "aura"
    coord.event_queue = queue.Queue()
    coord.logger = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None,
                                   debug=lambda *a, **k: None, error=lambda *a, **k: None)
    coord.direct_audio = DirectAudioService(llm, coord.config)
    coord.listener = SimpleNamespace(conversation_window_active=True, _capture_generation=1)
    coord._apply_speaker_context = lambda *a, **k: None
    coord._turn_cancelled = threading.Event()
    coord._llm_responded = False
    coord.state = PipelineState.IDLE
    return coord, llm


def test_transcript_of_finished_direct_turn_never_enters_text_path():
    coord, _ = make_coordinator()
    coord._valid_short_replies = set()
    coord._handle_transcription(Event(
        EventType.TRANSCRIPTION_READY,
        data={"text": "erzähl mir einen Witz", "speaker_id": None, "speaker_confidence": 0.0,
              "capture_generation": 1, "audio_turn_id": "a7"},
        source="stt_worker"))
    assert coord.event_queue.empty()             # no COMMAND_DETECTED via the legacy path


def test_privacy_flush_cancels_running_popped_turn():
    coord, llm = make_coordinator()
    at = coord.direct_audio.start_turn(AUDIO, in_conversation=True)
    assert llm.started.wait(1.0)
    coord.direct_audio.pop(at.turn_id, active=True)      # consumed by _handle_command right now
    coord.state = PipelineState.PROCESSING_COMMAND

    coord._privacy_flush_direct_audio()

    assert at.turn.is_rejected and llm.cancelled >= 1
    assert coord._turn_cancelled.is_set()
    assert at.audio is None and at.asr_hint is None and at.audio_b64 is None


def test_privacy_flush_cancels_registered_turns_and_hints():
    coord, llm = make_coordinator()
    at = coord.direct_audio.start_turn(AUDIO, in_conversation=False)
    coord.direct_audio.note_transcript(at.turn_id, "geheim")
    coord._privacy_flush_direct_audio()
    assert at.turn.is_rejected and at.asr_hint is None
    assert coord.direct_audio.get(at.turn_id) is None


def test_asr_hint_not_kept_when_content_logging_blocked():
    llm = FakeLLM()
    svc = DirectAudioService(llm, Cfg(**{"llm.primary.audio_direct": True}),
                             content_allowed=lambda: False)
    at = svc.start_turn(AUDIO, in_conversation=True)
    svc.note_transcript(at.turn_id, "geheim")
    assert at.asr_hint is None
    llm.release.set()
    svc.discard_all()


# --- asr_hint in the conversation history (finding 5) --------------------------------------------

def make_conversation(tmp_path, monkeypatch, content_allowed=True):
    from core import conversation as conv_mod
    conv = conv_mod.ConversationManager.__new__(conv_mod.ConversationManager)
    conv.session_history = []
    conv.session_participants = set()
    conv.current_user = "christopher"
    conv.logger = SimpleNamespace(debug=lambda *a, **k: None, error=lambda *a, **k: None,
                                  warning=lambda *a, **k: None, info=lambda *a, **k: None)
    conv._privacy_gate = SimpleNamespace(allow=lambda cap: content_allowed)
    conv.written = []
    conv._append_to_history_file = lambda message: conv.written.append(dict(message))
    conv.memory_seen = []
    conv._memory_manager = SimpleNamespace(on_message=lambda m: conv.memory_seen.append(dict(m)))
    conv._context_window = None
    conv.profile_manager = None
    conv.max_history_turns = 10
    conv.max_history_chars = 10000
    return conv


def test_asr_hint_reaches_history_and_memory_but_never_disk(tmp_path, monkeypatch):
    conv = make_conversation(tmp_path, monkeypatch)
    conv.add_message("user", "[Sprachnachricht a1]", asr_hint="wie wird das Wetter morgen",
                     audio_turn_id="a1", client_id="voice")

    msg = conv.session_history[-1]
    assert msg["asr_hint"] == "wie wird das Wetter morgen" and msg["audio_turn_id"] == "a1"
    assert "asr_hint" not in conv.written[-1]                    # never persisted
    assert conv.memory_seen[-1]["content"] == "wie wird das Wetter morgen"
    assert "asr_hint" not in conv.memory_seen[-1]


def test_asr_hint_dropped_when_content_logging_blocked(tmp_path, monkeypatch):
    conv = make_conversation(tmp_path, monkeypatch, content_allowed=False)
    conv.add_message("user", "[Sprachnachricht a1]", asr_hint="geheim", audio_turn_id="a1")
    assert "asr_hint" not in conv.session_history[-1]
    assert conv.memory_seen[-1]["content"] == "[Sprachnachricht a1]"


def test_history_for_llm_includes_asr_hint_for_followups(tmp_path, monkeypatch):
    conv = make_conversation(tmp_path, monkeypatch)
    conv.get_recent_history = lambda max_turns=None, target_history=None: list(conv.session_history)
    conv._format_timestamp_for_llm = lambda ts: "12:00"
    conv._get_speaker_label = lambda uid: "x"
    conv.add_message("user", "[Sprachnachricht a1]", asr_hint="wie wird das Wetter heute")
    text = conv.format_history_for_llm(include_system_prompt=False)
    assert "wie wird das Wetter heute" in text
