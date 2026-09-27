"""Active Qwen3/Chatterbox telemetry is aggregated without retaining speech content."""

import io
import os
import sys
import wave
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

from core.stt_qwen3 import Qwen3SpeechToText
from core.tts import TextToSpeech


class _NullLogger:
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass


def test_qwen3_emits_content_free_stt_metrics_and_does_not_log_transcript(monkeypatch, caplog):
    phrase = "private qwen transcript phrase"
    events = []

    class _EventLogger:
        def emit(self, **event):
            events.append(event)

    class _Stream:
        result = SimpleNamespace(text=phrase)

        def accept_waveform(self, *_args): pass

    stt = Qwen3SpeechToText.__new__(Qwen3SpeechToText)
    stt.logger = _NullLogger()
    stt.sample_rate = 16000
    stt.recognizer = SimpleNamespace(
        create_stream=lambda: _Stream(), decode_stream=lambda _stream: None
    )
    stt._prepare_audio = lambda audio, _rate: audio
    monkeypatch.setattr("core.event_logger.get_event_logger", lambda: _EventLogger())

    assert stt.transcribe(np.zeros(3200, dtype=np.float32)) == phrase
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "stt_transcription"
    assert event["status"] == "success"
    assert event["metadata"]["engine"] == "qwen3-asr"
    assert event["metadata"]["text_length"] == len(phrase)
    assert "text" not in event["metadata"]
    assert phrase not in repr(event)


def test_chatterbox_emits_content_free_tts_metrics(monkeypatch):
    phrase = "private chatterbox phrase"
    events = []

    class _EventLogger:
        def emit(self, **event):
            events.append(event)

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24000)
        wav_file.writeframes(b"\0\0" * 2400)

    class _Response:
        content = wav_buffer.getvalue()

    class _Session:
        def post(self, *_args, **_kwargs):
            return _Response()

    tts = TextToSpeech.__new__(TextToSpeech)
    tts._chatterbox_session = _Session()
    tts.chatterbox_endpoint = "http://127.0.0.1:8765/tts"
    tts.chatterbox_connect_timeout = 1
    tts.chatterbox_timeout = 5
    tts._chatterbox_available = lambda: True
    tts._chatterbox_record_success = lambda: None
    tts._chatterbox_record_failure = lambda: None
    tts.logger = _NullLogger()
    monkeypatch.setattr("core.event_logger.get_event_logger", lambda: _EventLogger())

    pcm, sample_rate = tts._chatterbox_generate_pcm(phrase)
    assert pcm is not None
    assert sample_rate == 24000
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "tts_synthesis"
    assert event["status"] == "success"
    assert event["metadata"]["engine"] == "chatterbox"
    assert event["metadata"]["text_length"] == len(phrase)
    assert "text" not in event["metadata"]
    assert phrase not in repr(event)
