"""Watchdog listener-stuck check: a soft reset bumps the capture generation and
would invalidate a direct-audio turn that is being collected/queued/answered.
It must only fire for a truly idle listener (no recent speech, no pending audio)."""

import os
import queue
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

from core.events import PipelineState
from core.watchdog import Watchdog


def make(**over):
    now = time.monotonic()
    wd = Watchdog.__new__(Watchdog)
    wd._listener_stuck_threshold = 60.0
    wd._listener_recent_speech_grace = 10.0
    wd._listener_idle_s = 0.0
    wd._listener = SimpleNamespace(
        running=True, speaking=False, _speaking_event=SimpleNamespace(is_set=lambda: False),
        collecting_speech=False, audio_queue=queue.Queue(),
        _last_vad_activity_ts=now - 200)
    wd._coordinator = SimpleNamespace(
        state=PipelineState.IDLE, _last_transcription_ts=now - 400, _last_idle_ts=now - 300,
        direct_audio=SimpleNamespace(_turns={}, _active={}))
    for key, value in over.items():
        target, attr = key.split("__")
        setattr(getattr(wd, target), attr, value)
    return wd


def test_truly_idle_listener_with_old_speech_is_stuck():
    assert make()._check_listener_stuck() is True


def test_silence_only_is_not_stuck():
    now = time.monotonic()
    wd = make(_listener___last_vad_activity_ts=now - 500)   # VAD older than last transcription
    assert wd._check_listener_stuck() is False


def test_collecting_speech_is_not_stuck():
    assert make(_listener__collecting_speech=True)._check_listener_stuck() is False


def test_queued_audio_is_not_stuck():
    wd = make()
    wd._listener.audio_queue.put(object())
    assert wd._check_listener_stuck() is False


def test_registered_or_running_direct_turn_is_not_stuck():
    assert make(_coordinator__direct_audio=SimpleNamespace(_turns={"a1": 1}, _active={}))._check_listener_stuck() is False
    assert make(_coordinator__direct_audio=SimpleNamespace(_turns={}, _active={"a1": 1}))._check_listener_stuck() is False


def test_recent_speech_grace_window():
    wd = make(_listener___last_vad_activity_ts=time.monotonic() - 3)
    wd._coordinator._last_transcription_ts = time.monotonic() - 400
    assert wd._check_listener_stuck() is False


def test_idle_is_measured_from_latest_of_transcription_idle_and_vad():
    now = time.monotonic()
    wd = make(_listener___last_vad_activity_ts=now - 30)
    wd._coordinator._last_transcription_ts = now - 900
    wd._coordinator._last_idle_ts = now - 50            # recently finished a turn
    assert wd._check_listener_stuck() is False          # baseline = vad (30 s) < 60 s
    wd._listener._last_vad_activity_ts = now - 90
    wd._coordinator._last_idle_ts = now - 120
    assert wd._check_listener_stuck() is True and 85 < wd._listener_idle_s < 100
