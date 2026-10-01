"""Observe software playback boundaries without audio, providers or devices."""
import io
import queue
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from core.pipeline import Coordinator, StreamingAudioPipeline, _ChatterboxAudioWriter
from core.latency_tracker import LatencyTracker
from core.tts import TextToSpeech


def test_writer_queueing_is_not_output_and_callback_follows_pcm_write():
    order = []
    player = SimpleNamespace(
        stdin=SimpleNamespace(write=lambda pcm: order.append("write"), close=Mock()),
        wait=Mock(return_value=0))
    tts = SimpleNamespace(sample_rate=24000, _open_aplay=lambda: player,
                          _track_proc=Mock())
    writer = _ChatterboxAudioWriter(tts, Mock(), lambda: order.append("output"))
    writer.submit(b"\x00\x00", 24000)
    assert order == []
    writer._queue.put(None)
    writer._run()
    assert order == ["write", "output"]


def test_failed_pcm_write_never_marks_output():
    player = SimpleNamespace(stdin=SimpleNamespace(
        write=Mock(side_effect=BrokenPipeError()), close=Mock()))
    tts = SimpleNamespace(sample_rate=24000, _open_aplay=lambda: player, _track_proc=Mock())
    output = Mock()
    writer = _ChatterboxAudioWriter(tts, Mock(), output)
    writer.submit(b"\x00\x00", 24000)
    writer._run()
    output.assert_not_called()


def test_observer_failure_never_breaks_pcm_playback():
    player = SimpleNamespace(stdin=SimpleNamespace(write=Mock(), close=Mock()))
    tts = SimpleNamespace(sample_rate=24000, _open_aplay=lambda: player, _track_proc=Mock())
    writer = _ChatterboxAudioWriter(tts, Mock(), Mock(side_effect=RuntimeError("synthetic")))
    writer.submit(b"\x00\x00", 24000)
    writer._queue.put(None)
    writer._run()
    assert writer.error is None
    assert writer.total_samples == 1


def test_output_observer_is_scoped_to_thread_and_restores_previous():
    tts = TextToSpeech.__new__(TextToSpeech)
    tts._output_observers = threading.local()
    outer, inner = Mock(), Mock()
    with tts.observe_output(outer):
        tts._notify_output_start()
        other = threading.Thread(target=tts._notify_output_start)
        other.start()
        other.join()
        with tts.observe_output(inner):
            tts._notify_output_start()
        tts._notify_output_start()
    tts._notify_output_start()
    assert outer.call_count == 2
    inner.assert_called_once()


def test_synchronous_command_observes_output_without_changing_completion():
    tts = TextToSpeech.__new__(TextToSpeech)
    def speak(text):
        tts._notify_output_start()
        assert coordinator._current_latency.has("tts_output_start")
        assert not coordinator._current_latency.has("tts_complete")
        return True
    tts.speak = speak
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.tts = tts
    coordinator.listener = SimpleNamespace(speaking=False, active_tts_text="")
    coordinator._current_latency = LatencyTracker("synthetic-output")
    coordinator._speak_and_wait("synthetic")
    assert coordinator._current_latency.has("tts_complete")
    assert not coordinator._current_latency.has("tts_first_pcm")


def test_cancelled_stream_does_not_publish_output():
    output = Mock()
    pipeline = StreamingAudioPipeline(SimpleNamespace(), Mock(), output)
    pipeline._cancelled.set()
    pipeline._fire_first_audio_callback()
    output.assert_not_called()


def test_windows_bridge_acknowledges_playback_call_before_completion(tmp_path, monkeypatch):
    tts = TextToSpeech.__new__(TextToSpeech)
    tts.windows_temp_dir = tmp_path
    tts.logger = Mock()
    tts._track_proc = Mock()
    tts._untrack_proc = Mock()
    output = Mock()
    process = SimpleNamespace(stdout=io.BytesIO(b"JARVIS_PLAYBACK_CALL\n"),
                              stderr=io.BytesIO(), wait=Mock(return_value=0))
    monkeypatch.setattr("core.tts.subprocess.run", lambda *a, **kw: SimpleNamespace(stdout="C:\\synthetic.wav"))
    popen = Mock(return_value=process)
    monkeypatch.setattr("core.tts.subprocess.Popen", popen)
    with tts.observe_output(output):
        assert tts._play_wav_windows(b"RIFF-synthetic")
    output.assert_called_once()
    command = popen.call_args.args[0][-1]
    assert command.index("$sp.Load()") < command.index("JARVIS_PLAYBACK_CALL") < command.index("$sp.PlaySync()")
    assert not list(tmp_path.iterdir())


def test_windows_failure_before_marker_has_no_output_observation(tmp_path, monkeypatch):
    tts = TextToSpeech.__new__(TextToSpeech)
    tts.windows_temp_dir = tmp_path
    tts.logger = Mock()
    tts._track_proc = Mock()
    tts._untrack_proc = Mock()
    output = Mock()
    process = SimpleNamespace(stdout=io.BytesIO(), stderr=io.BytesIO(b"synthetic"),
                              wait=Mock(return_value=1))
    monkeypatch.setattr("core.tts.subprocess.run", lambda *a, **kw: SimpleNamespace(stdout="C:\\synthetic.wav"))
    monkeypatch.setattr("core.tts.subprocess.Popen", lambda *a, **kw: process)
    with tts.observe_output(output):
        assert not tts._play_wav_windows(b"RIFF-synthetic")
    output.assert_not_called()


def test_contextual_acknowledgement_logs_metadata_without_content():
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.logger = Mock()
    coordinator.listener = SimpleNamespace(pause_listening=Mock())
    coordinator.tts = SimpleNamespace(speak=Mock(return_value=True))
    coordinator._llm_responded = False
    coordinator._contextual_ack_text = "synthetic-private-acknowledgement-marker"
    coordinator._play_ack_if_still_thinking("synthetic")
    coordinator.tts.speak.assert_called_once()
    assert coordinator._contextual_ack_text not in str(coordinator.logger.mock_calls)
    coordinator.logger.info.assert_called_once_with(
        "Contextual acknowledgement (%d chars)", len(coordinator._contextual_ack_text))
