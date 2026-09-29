"""Stop fast path outside TTS: a stop-only transcript cancels the speculative/running Gemma
direct-audio turn, drops the held aggregated audio and creates NO new LLM turn. A
fast_stop_candidate whose STT is NOT stop-only proceeds as a normal turn (no loss)."""

import queue
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from core.continuous_listener import ContinuousListener
from core.direct_audio import DirectAudioService
from core.events import EventType, PipelineState
from core.llm_router import LLMRouter
from core.pipeline import Coordinator, STTWorker
from core.turn_assembler import TurnAssembler


class Cfg:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


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
        yield "Welt"

    def cancel_active_stream(self):
        self.cancelled += 1
        self.release.set()


class FakeListener:
    def __init__(self):
        self._speaking_event = threading.Event()
        self._capture_generation = 1
        self.conversation_window_active = True
        self.discards = 0
        self.assembler = TurnAssembler(grace_s=5.0)

    def discard_held_turn(self):
        self.discards += 1
        self.assembler.discard()


AUDIO = np.ones(16000, dtype=np.float32)
LONG = np.ones(40000, dtype=np.float32)   # > fast_stop_max_s: held by the assembler


def make_coord(gate=False):
    llm = FakeLLM()
    coord = Coordinator.__new__(Coordinator)
    coord.wake_word = "aura"
    coord.llm = llm
    coord.listener = FakeListener()
    coord.tts = SimpleNamespace(interrupts=0)
    coord.tts.interrupt_active = lambda: setattr(coord.tts, "interrupts", coord.tts.interrupts + 1)
    coord.direct_audio = DirectAudioService(
        llm, Cfg(**{"llm.primary.audio_direct": True, "stt.wake_compat": gate}))
    coord.event_queue = queue.Queue()
    coord._turn_cancelled = threading.Event()
    coord._stop_only_interrupt = False
    coord._llm_responded = False
    coord._active_audio_pipeline = None
    coord.state = PipelineState.IDLE
    coord.logger = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None,
                                   debug=lambda *a, **k: None, error=lambda *a, **k: None)
    return coord, llm


@pytest.mark.parametrize("text", ["Aura stopp", "stopp bitte", "Aura, stopp bitte", "stopp"])
def test_stop_only_cancels_speculative_turn_discards_assembler_and_makes_no_turn(text):
    coord, llm = make_coord(gate=True)
    at = coord.direct_audio.start_turn(AUDIO, in_conversation=False)   # speculative Gemma request
    assert llm.started.wait(1.0)
    coord.listener.assembler.add(LONG, generation=1)                   # held merge buffer
    assert coord.listener.assembler.pending == 1

    assert coord.handle_stop_only(text, at) is True

    assert llm.cancelled >= 1                                  # Gemma request cancelled
    assert coord.direct_audio.get(at.turn_id) is None
    assert coord.listener.discards == 1 and coord.listener.assembler.pending == 0
    assert coord.tts.interrupts == 1                           # TTS interrupted as today
    assert coord.event_queue.empty()                           # no new LLM turn / command


def test_stop_only_marks_running_turn_cancelled():
    coord, _ = make_coord()
    coord.state = PipelineState.PROCESSING_COMMAND
    assert coord.handle_stop_only("Aura stopp") is True
    assert coord._turn_cancelled.is_set() and coord._stop_only_interrupt


@pytest.mark.parametrize("text", ["Aura wie spät ist es", "stopp die Musik bitte nicht", "danke", ""])
def test_non_stop_transcript_is_not_consumed(text):
    coord, llm = make_coord()
    assert coord.handle_stop_only(text) is False
    assert llm.cancelled == 0 and coord.listener.discards == 0


def test_during_tts_stays_with_barge_in_path():
    coord, llm = make_coord()
    coord.listener._speaking_event.set()
    assert coord.handle_stop_only("Aura stopp") is False       # handle_barge_in owns it
    assert llm.cancelled == 0


# --- STTWorker: deferral + no loss -----------------------------------------------------------

class FakeSTT:
    def __init__(self, text):
        self.text = text

    def transcribe(self, audio, sr, **kw):
        return self.text


def run_worker(coord, text, fast=True):
    events = queue.Queue()
    audio_queue = queue.Queue()
    worker = STTWorker(FakeSTT(text), events, audio_queue, config=None, listener=coord.listener)
    worker.on_audio_turn = coord.start_direct_audio_turn
    worker.on_audio_turn_reject = coord.reject_audio_turn
    worker.on_stop_only = coord.handle_stop_only
    audio_queue.put({"audio": AUDIO, "capture_generation": 1, "during_tts": False,
                     "fast_stop_candidate": fast, "turn_id": 1})
    audio_queue.put(None)
    worker.start()
    worker.join(5)
    return [events.get_nowait() for _ in range(events.qsize())]


def test_stt_stop_only_fast_candidate_creates_no_command_and_cancels_gemma():
    coord, llm = make_coord()            # conversation window: no wake gate
    events = run_worker(coord, "Aura stopp")
    assert [e.type for e in events] == []                      # neither COMMAND nor TRANSCRIPTION
    assert llm.cancelled >= 1
    assert coord.listener.discards == 1


def test_fast_stop_candidate_that_is_not_stop_proceeds_as_normal_turn():
    coord, llm = make_coord()
    events = run_worker(coord, "ja genau")
    types = [e.type for e in events]
    assert EventType.COMMAND_DETECTED in types and EventType.TRANSCRIPTION_READY in types
    command = next(e for e in events if e.type is EventType.COMMAND_DETECTED)
    assert command.data["direct_audio_turn"]                   # the same Gemma turn, not lost
    assert llm.cancelled == 0 and coord.direct_audio.get(command.data["direct_audio_turn"]) is not None


def test_fast_stop_candidate_with_blank_stt_still_dispatches_the_turn():
    coord, llm = make_coord()
    events = run_worker(coord, "")
    assert [e.type for e in events] == [EventType.COMMAND_DETECTED]


def test_non_candidate_segment_dispatches_command_immediately():
    coord, _ = make_coord()
    events = run_worker(coord, "erzähl mir was", fast=False)
    assert events[0].type is EventType.COMMAND_DETECTED


# --- listener method ----------------------------------------------------------------------------

def test_listener_discard_held_turn_drops_buffer_without_release():
    listener = ContinuousListener.__new__(ContinuousListener)
    listener._turn_lock = threading.Lock()
    listener._turn_assembler = TurnAssembler(grace_s=0.0)
    listener._turn_assembler.add(LONG, generation=1)
    assert listener._turn_assembler.pending == 1
    listener.discard_held_turn()
    time.sleep(0.01)
    assert listener._turn_assembler.pending == 0
    assert listener._turn_assembler.poll() is None
    ContinuousListener.discard_held_turn(SimpleNamespace(_turn_assembler=None, _turn_lock=threading.Lock()))


# --- no ambient stop / conversation-window stop while a direct turn runs ------------------------

def test_ambient_stop_without_wake_window_or_running_turn_is_not_consumed():
    coord, llm = make_coord()
    coord.listener.conversation_window_active = False
    assert coord.handle_stop_only("stopp") is False
    assert llm.cancelled == 0 and coord.listener.discards == 0 and coord.tts.interrupts == 0


def test_ambient_stop_does_not_cancel_own_speculative_turn_without_wake():
    coord, llm = make_coord(gate=True)
    coord.listener.conversation_window_active = False
    at = coord.direct_audio.start_turn(AUDIO, in_conversation=False)
    assert llm.started.wait(1.0)
    assert coord.handle_stop_only("halt", at) is False      # its own turn is no "running turn"
    assert llm.cancelled == 0


def test_stop_with_wake_word_is_consumed_without_window():
    coord, llm = make_coord()
    coord.listener.conversation_window_active = False
    assert coord.handle_stop_only("Aura stopp") is True


def test_stop_in_conversation_window_cancels_running_direct_turn_and_makes_no_turn():
    coord, llm = make_coord()                                  # window active, ungated
    at = coord.direct_audio.start_turn(AUDIO, in_conversation=True)
    popped = coord.direct_audio.pop(at.turn_id, active=True)   # answer is running right now
    assert popped is at and llm.started.wait(1.0)
    coord.state = PipelineState.PROCESSING_COMMAND
    stop_segment = coord.direct_audio.start_turn(AUDIO, in_conversation=True)

    assert coord.handle_stop_only("stopp", stop_segment) is True

    assert at.turn.is_rejected and llm.cancelled >= 1          # running stream cancelled
    assert coord._turn_cancelled.is_set() and coord._stop_only_interrupt
    assert coord.event_queue.empty()                           # no new LLM turn
    assert coord.direct_audio.active_turns() == []
