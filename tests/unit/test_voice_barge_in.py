"""Regression tests for the voice pipeline's interrupt and stale-audio gates."""

import queue
import threading
import time
from types import SimpleNamespace

from core.events import Event, EventType, PipelineState
from core.llm_router import LLMRouter
from core.pipeline import Coordinator, STTWorker, StreamingAudioPipeline
from core.continuous_listener import ContinuousListener


class NullLogger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class FakeListener:
    def __init__(self):
        self._speaking_event = threading.Event()
        self._speaking_event.set()
        self._capture_generation = 4
        self.active_tts_text = ""
        self.conversation_window_active = True
        self._extended_duration = 12
        self.windows_opened = []
        self.invalidations = 0
        self.resumes = 0

    def invalidate_pending_audio(self):
        self._capture_generation += 1
        self.invalidations += 1

    def resume_listening(self):
        self._speaking_event.clear()
        self.resumes += 1

    def open_conversation_window(self, duration):
        self.windows_opened.append(duration)
        self.conversation_window_active = True


class FakeTTS:
    def __init__(self):
        self.interrupts = 0

    def interrupt_active(self):
        self.interrupts += 1


class FakeLLM:
    def __init__(self):
        self.cancellations = 0

    def cancel_active_stream(self):
        self.cancellations += 1


def _coordinator_for_interrupt(listener=None):
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.listener = listener or FakeListener()
    coordinator.tts = FakeTTS()
    coordinator.llm = FakeLLM()
    coordinator.event_queue = queue.Queue()
    coordinator._turn_cancelled = threading.Event()
    coordinator._active_audio_pipeline = None
    coordinator._active_response_text = ""
    coordinator._barge_in_lock = threading.Lock()
    coordinator.wake_word = "jarvis"
    coordinator.logger = NullLogger()
    return coordinator


def test_barge_in_requires_wake_word_and_rejects_tts_echo():
    coordinator = _coordinator_for_interrupt()
    coordinator._active_response_text = "Jarvis, hier ist die Antwort."

    assert not coordinator.handle_barge_in("Jarvis hier ist die Antwort")
    assert not coordinator.handle_barge_in("Bitte stoppe jetzt")
    assert not coordinator._turn_cancelled.is_set()
    assert coordinator.event_queue.empty()
    assert coordinator.tts.interrupts == 0


def test_barge_in_stops_owned_outputs_and_queues_user_input_once():
    coordinator = _coordinator_for_interrupt()
    coordinator._active_response_text = "Die Antwort läuft gerade."
    pipeline = SimpleNamespace(cancel_calls=0, cancel=lambda: setattr(
        pipeline, "cancel_calls", pipeline.cancel_calls + 1,
    ))
    coordinator._active_audio_pipeline = pipeline

    assert coordinator.handle_barge_in("Jarvis, stopp bitte", "alex", 0.9)
    assert not coordinator.handle_barge_in("Jarvis, stopp bitte", "alex", 0.9)

    event = coordinator.event_queue.get_nowait()
    assert event.type is EventType.TRANSCRIPTION_READY
    assert event.source == "barge_in"
    assert event.data["text"] == "Jarvis, stopp bitte"
    assert event.data["barge_in"] is True
    assert coordinator.tts.interrupts == 1
    assert coordinator.llm.cancellations == 1
    assert pipeline.cancel_calls == 1
    assert coordinator.listener.invalidations == 1
    assert coordinator.event_queue.empty()


def test_bare_stopp_during_first_chunk_cancels_without_queued_command():
    coordinator = _coordinator_for_interrupt()
    coordinator.listener.active_tts_text = "Die erste Antwort läuft."
    pipeline = SimpleNamespace(cancel_calls=0, cancel=lambda: setattr(
        pipeline, "cancel_calls", pipeline.cancel_calls + 1,
    ))
    coordinator._active_audio_pipeline = pipeline

    assert coordinator.handle_barge_in("Stopp")
    assert not coordinator.handle_barge_in("Stopp")
    assert pipeline.cancel_calls == 1
    assert coordinator.tts.interrupts == 1
    assert coordinator.llm.cancellations == 1
    assert coordinator.listener.invalidations == 1
    assert coordinator.event_queue.empty()

    coordinator._active_audio_pipeline = None
    coordinator._streaming_active = True
    coordinator.state = PipelineState.SPEAKING
    coordinator._finish_cancelled_turn()
    assert coordinator.listener.resumes == 1
    assert coordinator.listener.windows_opened == [12]
    assert coordinator.listener.conversation_window_active
    assert not coordinator.listener._speaking_event.is_set()
    assert not coordinator._turn_cancelled.is_set()


def test_bare_halt_during_later_chunk_discards_pending_audio():
    coordinator = _coordinator_for_interrupt()
    coordinator.listener.active_tts_text = "Der zweite Abschnitt läuft gerade."
    pipeline = SimpleNamespace(cancel_calls=0, cancel=lambda: setattr(
        pipeline, "cancel_calls", pipeline.cancel_calls + 1,
    ))
    coordinator._active_audio_pipeline = pipeline

    assert coordinator.handle_barge_in("Halt")
    assert pipeline.cancel_calls == 1
    assert coordinator.tts.interrupts == 1
    assert coordinator.llm.cancellations == 1
    assert coordinator.event_queue.empty()


def test_bare_stop_rejects_ordinary_speech_and_tts_echo():
    coordinator = _coordinator_for_interrupt()
    coordinator.listener.active_tts_text = "Sagen Sie Stopp, wenn Sie abbrechen möchten."

    assert not coordinator.handle_barge_in("Morgen habe ich Zeit")
    assert not coordinator.handle_barge_in("Stopp")
    assert coordinator.tts.interrupts == 0
    assert coordinator.event_queue.empty()

    coordinator.listener.active_tts_text = "Die Antwort läuft."
    assert coordinator.handle_barge_in("Stop")


def test_cancelled_turn_resets_speaking_and_preserves_conversation_window():
    coordinator = _coordinator_for_interrupt()
    coordinator._turn_cancelled.set()
    coordinator.state = PipelineState.SPEAKING
    coordinator._active_audio_pipeline = None
    coordinator._streaming_active = True
    coordinator._llm_responded = True
    coordinator._last_command_end_ts = 0
    coordinator._last_idle_ts = 0

    coordinator._finish_cancelled_turn()

    assert coordinator.listener.resumes == 1
    assert not coordinator.listener._speaking_event.is_set()
    assert coordinator.listener.conversation_window_active is True
    assert coordinator.state is PipelineState.IDLE
    assert coordinator._streaming_active is False
    assert coordinator._llm_responded is True
    assert not coordinator._turn_cancelled.is_set()


def test_llm_stream_cancellation_closes_only_active_response():
    class Response:
        closed = False

        def close(self):
            self.closed = True

    router = LLMRouter.__new__(LLMRouter)
    router._active_stream_lock = threading.Lock()
    router._active_stream_response = Response()
    router._stream_cancel_event = threading.Event()
    response = router._active_stream_response

    router.cancel_active_stream()

    assert response.closed is True
    assert router._active_stream_response is None


def test_stt_drops_stale_capture_and_dispatches_valid_barge_once():
    audio_queue = queue.Queue()
    event_queue = queue.Queue()
    listener = SimpleNamespace(_capture_generation=4)

    class STT:
        calls = 0

        def transcribe(self, audio, sample_rate):
            self.calls += 1
            return "Jarvis, stopp bitte"

    stt = STT()
    worker = STTWorker(stt, event_queue, audio_queue, listener=listener)
    accepted = []

    def on_barge(text, speaker_id, confidence):
        accepted.append(text)
        event_queue.put(Event(
            EventType.TRANSCRIPTION_READY,
            data={"text": text, "barge_in": True},
            source="barge_in",
        ))
        return True

    worker.on_barge_in = on_barge
    audio_queue.put({"audio": object(), "capture_generation": 3, "during_tts": True})
    audio_queue.put({"audio": object(), "capture_generation": 4, "during_tts": True})
    audio_queue.put(None)
    worker.run()

    assert stt.calls == 1
    assert accepted == ["Jarvis, stopp bitte"]
    event = event_queue.get_nowait()
    assert event.source == "barge_in"
    assert event.data["text"] == "Jarvis, stopp bitte"
    assert event_queue.empty()


def test_stt_drops_transcription_that_becomes_stale_while_recognizing():
    event_queue = queue.Queue()
    audio_queue = queue.Queue()
    listener = SimpleNamespace(_capture_generation=8)

    class STT:
        def transcribe(self, audio, sample_rate):
            listener._capture_generation += 1
            return "Jarvis, stop"

    audio_queue.put({"audio": object(), "capture_generation": 8, "during_tts": False})
    audio_queue.put(None)
    STTWorker(STT(), event_queue, audio_queue, listener=listener).run()

    assert event_queue.empty()


def test_listener_invalidation_clears_queued_audio_but_preserves_shutdown():
    listener = ContinuousListener.__new__(ContinuousListener)
    listener.audio_queue = queue.Queue()
    listener._buffer_lock = threading.Lock()
    listener._capture_generation = 2
    listener.audio_queue.put({"audio": object(), "capture_generation": 2})
    listener.audio_queue.put(None)

    listener.invalidate_pending_audio()

    assert listener._capture_generation == 3
    assert listener.audio_queue.get_nowait() is None
    assert listener.audio_queue.empty()


def test_streaming_pipeline_cancellation_discards_inflight_result_and_piper_fallback():
    generation_started = threading.Event()
    release_generation = threading.Event()

    class SlowTTS:
        engine = "chatterbox"
        sample_rate = 24000
        normalization_enabled = False
        normalizer = None
        output_backend = "windows"

        def __init__(self):
            self._tts_lock = threading.Lock()
            self.piper_calls = []
            self.played = []
            self.interrupts = 0

        def _chatterbox_generate_pcm(self, text):
            generation_started.set()
            release_generation.wait(3)
            return None, None

        def _piper_generate_pcm(self, text):
            self.piper_calls.append(text)
            return b"\x01\x00" * 20, 24000

        def _play_pcm_windows(self, pcm, rate):
            self.played.append((pcm, rate))
            return True

        def interrupt_active(self):
            self.interrupts += 1

    tts = SlowTTS()
    pipeline = StreamingAudioPipeline(tts, NullLogger())
    pipeline.start()
    pipeline.put("first sentence")
    assert generation_started.wait(1)
    pipeline.put("second sentence")
    pipeline.cancel()
    release_generation.set()
    pipeline._thread.join(timeout=3)
    assert not pipeline._thread.is_alive()
    assert pipeline._done.is_set()
    assert tts.interrupts == 1
    assert tts.piper_calls == []
    assert tts.played == []
    assert pipeline._writer._thread.is_alive() is False


def test_streaming_pipeline_interrupt_during_later_windows_chunk_drops_next_chunk():
    second_playback_started = threading.Event()
    release_playback = threading.Event()

    class PlaybackTTS:
        engine = "chatterbox"
        sample_rate = 24000
        normalization_enabled = False
        normalizer = None
        output_backend = "windows"

        def __init__(self):
            self._tts_lock = threading.Lock()
            self.played = []
            self.interrupts = 0

        def _chatterbox_generate_pcm(self, text):
            return text.encode(), 24000

        def _play_pcm_windows(self, pcm, rate):
            self.played.append(pcm.decode())
            if len(self.played) == 2:
                second_playback_started.set()
                release_playback.wait(2)
            return True

        def interrupt_active(self):
            self.interrupts += 1
            release_playback.set()

    tts = PlaybackTTS()
    pipeline = StreamingAudioPipeline(tts, NullLogger())
    pipeline.start()
    for sentence in ("first", "second", "third"):
        pipeline.put(sentence)
    assert second_playback_started.wait(1)
    pipeline.cancel()
    pipeline._thread.join(timeout=3)

    assert not pipeline._thread.is_alive()
    assert pipeline._writer._thread.is_alive() is False
    assert tts.played == ["first", "second"]
    assert tts.interrupts == 1


def test_streaming_pipeline_interrupt_during_first_windows_playback_stops_immediately():
    playback_started = threading.Event()
    release_playback = threading.Event()

    class PlaybackTTS:
        engine = "chatterbox"
        sample_rate = 24000
        normalization_enabled = False
        normalizer = None
        output_backend = "windows"

        def __init__(self):
            self._tts_lock = threading.Lock()
            self.played = []
            self.interrupts = 0

        def _chatterbox_generate_pcm(self, text):
            return text.encode(), 24000

        def _play_pcm_windows(self, pcm, rate):
            self.played.append(pcm.decode())
            playback_started.set()
            release_playback.wait(2)
            return True

        def interrupt_active(self):
            self.interrupts += 1
            release_playback.set()

    tts = PlaybackTTS()
    pipeline = StreamingAudioPipeline(tts, NullLogger())
    pipeline.start()
    pipeline.put("first")
    pipeline.put("second")
    assert playback_started.wait(1)
    pipeline.cancel()
    pipeline._thread.join(timeout=3)

    assert not pipeline._thread.is_alive()
    assert pipeline._writer._thread.is_alive() is False
    assert tts.played == ["first"]
    assert tts.interrupts == 1
