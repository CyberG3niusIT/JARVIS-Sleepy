"""Unit tests for session #6 P0 item 1: audio privacy must reset the
VAD ring buffer and Silero state, not just gate the speech-collection
handoff.

Session #5 gated `continuous_listener._on_speech_start()`/`_process_speech()`
(the speech-collection handoff) and registered a flush callback that
cleared `speech_buffer`/`_pre_speech_audio` — but `_audio_callback()`
still fed every raw frame into `VoiceActivityDetector.process_frame()`
unconditionally, which appends to `vad.audio_buffer` (a ring buffer later
read by `_on_speech_start()` as the pre-speech snapshot) regardless of
privacy mode. That meant audio recorded *during* PRIVACY could still be
sitting in the ring buffer and leak into the very first utterance
captured right after exit.

`core/continuous_listener.py` cannot be imported in this sandbox (it
imports `sounddevice` at module scope, which needs the PortAudio native
library — confirmed absent, same pre-existing gap noted in session #5's
work). These tests instead verify the primitives the fix depends on
directly against the real `core/vad.py` (no mocking): that
`VoiceActivityDetector.clear_buffer()` actually empties `audio_buffer`
and that `reset()` actually resets speech/silence counters and
`is_speech` — the exact two calls `continuous_listener.py`'s
`_privacy_flush_speech_buffer()` now makes on every PrivacyGate
enter()/exit() (see that method's docstring).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import numpy as np
import pytest

from core.vad import VoiceActivityDetector


class _FakeConfig(dict):
    def get(self, path, default=None):
        parts = path.split(".")
        d = self
        for p in parts:
            if isinstance(d, dict) and p in d:
                d = d[p]
            else:
                return default
        return d


@pytest.fixture
def vad():
    cfg = _FakeConfig({"vad": {"aggressiveness": 2, "buffer_duration": 1.0}})
    return VoiceActivityDetector(cfg)


class TestClearBufferRemovesBufferedAudio:
    def test_clear_buffer_empties_ring_buffer(self, vad):
        frame = np.zeros(vad.frame_size, dtype=np.int16)
        for _ in range(5):
            vad.audio_buffer.append(frame.copy())
        assert len(vad.audio_buffer) == 5

        vad.clear_buffer()

        assert len(vad.audio_buffer) == 0
        assert vad.get_buffered_audio().size == 0

    def test_clear_buffer_prevents_pre_speech_leak(self, vad):
        """Simulates the exact leak: audio buffered before a privacy
        transition must not be readable via get_buffered_audio() (what
        _on_speech_start() uses for the pre-speech snapshot) after the
        flush callback runs."""
        privacy_era_frame = np.full(vad.frame_size, 12345, dtype=np.int16)
        vad.audio_buffer.append(privacy_era_frame)
        assert vad.get_buffered_audio().size > 0

        vad.clear_buffer()  # what _privacy_flush_speech_buffer() calls

        assert vad.get_buffered_audio().size == 0


class TestResetClearsSpeechState:
    def test_reset_clears_frame_counters_and_speech_flag(self, vad):
        vad.speech_frames = 7
        vad.silence_frames = 3
        vad.is_speech = True

        vad.reset()

        assert vad.speech_frames == 0
        assert vad.silence_frames == 0
        assert vad.is_speech is False

    def test_reset_is_safe_with_no_model_loaded(self, vad):
        # _model is None until process_frame() lazily loads Silero — reset()
        # must not require a loaded model (a privacy enter/exit before any
        # speech was ever processed must not crash).
        assert vad._model is None
        vad.reset()  # must not raise

    def test_reset_calls_model_reset_states_when_model_present(self, vad):
        calls = []

        class _FakeModel:
            def reset_states(self):
                calls.append("reset")

        vad._model = _FakeModel()
        vad.reset()

        assert calls == ["reset"]


class TestFlushSequenceMatchesPrivacyGateCallback:
    """Mirrors exactly what continuous_listener._privacy_flush_speech_buffer()
    does to the VAD (clear_buffer() then reset()) — verifies the sequence
    leaves the VAD in a fully clean state, since that method can't be
    exercised directly in this sandbox (see module docstring)."""

    def test_clear_then_reset_leaves_fully_clean_state(self, vad):
        frame = np.ones(vad.frame_size, dtype=np.int16)
        vad.audio_buffer.append(frame)
        vad.speech_frames = 4
        vad.silence_frames = 2
        vad.is_speech = True

        vad.clear_buffer()
        vad.reset()

        assert len(vad.audio_buffer) == 0
        assert vad.speech_frames == 0
        assert vad.silence_frames == 0
        assert vad.is_speech is False
