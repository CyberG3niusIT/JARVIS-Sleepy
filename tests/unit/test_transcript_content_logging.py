"""Voice diagnostics must not persist or print raw speech content."""

import logging
import os
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

from core.continuous_listener import ContinuousListener
from core.pipeline import Coordinator
from core.stt import SpeechToText


def test_stt_event_contains_transcript_length_not_transcript(monkeypatch):
    recorded = []

    class _Logger:
        def debug(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass
        def warning(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass

    class _Model:
        def transcribe(self, *args, **kwargs):
            return [SimpleNamespace(text="utterance contains private-secret-phrase")], SimpleNamespace(
                language_probability=0.99
            )

    stt = SpeechToText.__new__(SpeechToText)
    stt.models = {"default": _Model()}
    stt.logger = _Logger()
    stt.language = "de"
    stt.debug_save_audio = False
    stt._trim_leading_silence = lambda audio: audio
    stt._apply_gain = lambda audio: audio

    class _Events:
        def emit(self, **event):
            recorded.append(event)

    monkeypatch.setattr("core.event_logger.get_event_logger", lambda: _Events())

    assert stt.transcribe(np.zeros(32, dtype=np.float32)) == "utterance contains private-secret-phrase"
    assert recorded
    assert recorded[0]["metadata"]["text_length"] == len(
        "utterance contains private-secret-phrase"
    )
    assert "text" not in recorded[0]["metadata"]
    assert "private-secret-phrase" not in repr(recorded[0])


def test_continuous_listener_does_not_log_or_print_transcript(caplog, monkeypatch):
    phrase = "jarvis, private-secret-phrase"
    listener = ContinuousListener.__new__(ContinuousListener)
    listener.logger = logging.getLogger("test.voice.transcript_privacy")
    listener.stt = SimpleNamespace(transcribe=lambda *args, **kwargs: phrase)
    listener.sample_rate = 16000
    listener._conversation_lock = threading.Lock()
    listener.conversation_window_active = False
    listener.wake_word = "jarvis"
    listener._apply_transcription_corrections = lambda text: text
    listener._is_ambient_wake_word = lambda text, word: False
    delivered = []
    listener.on_command = delivered.append

    with caplog.at_level(logging.INFO, logger="test.voice.transcript_privacy"):
        listener._transcribe_and_check(np.zeros(8, dtype=np.float32))

    assert delivered == ["private-secret-phrase"]
    assert "private-secret-phrase" not in caplog.text


def test_coordinator_does_not_log_or_print_transcript(caplog, monkeypatch):
    phrase = "jarvis, private-secret-phrase"
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.logger = logging.getLogger("test.pipeline.transcript_privacy")
    coordinator.listener = SimpleNamespace(conversation_window_active=False)
    coordinator.wake_word = "jarvis"
    coordinator._apply_transcription_corrections = lambda text: text
    coordinator._is_ambient_wake_word = lambda text, word: False
    coordinator.event_queue = Mock()

    with caplog.at_level(logging.INFO, logger="test.pipeline.transcript_privacy"):
        coordinator._handle_transcription(SimpleNamespace(data=phrase))

    queued_event = coordinator.event_queue.put.call_args.args[0]
    assert queued_event.data == "private-secret-phrase"
    assert "private-secret-phrase" not in caplog.text
