"""Unit tests for session #6 P0 item 2: webcam privacy must stop a
running capture on privacy enter, drop buffered frames, and gate
get_frame()/stream_frames() (not just start()).

core/webcam_manager.py has no sounddevice/torch dependency — importable
and testable for real in this sandbox, unlike continuous_listener.py.
Real asyncio event loop via pytest-asyncio-free `asyncio.run()` — the
ffmpeg subprocess itself is never actually started; tests exercise the
manager's own state machine by driving _running/_current_frame directly
and monkeypatching the pieces that would touch a real device/process.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.webcam_manager import WebcamManager
from core.privacy_gate import (
    Capability,
    PrivacyMode,
    get_privacy_gate,
    reset_privacy_gate_singleton_for_tests,
)


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


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_privacy_gate_singleton_for_tests()
    yield
    reset_privacy_gate_singleton_for_tests()


@pytest.fixture
def cfg():
    return _FakeConfig({"vision": {"webcam_device": "/dev/video0", "webcam_fps": 15}})


def _run(coro):
    return asyncio.run(coro)


class TestGetFrameDeniedDuringPrivacy:
    def test_get_frame_raises_permission_error_in_privacy(self, cfg):
        wm = WebcamManager(cfg)
        gate = get_privacy_gate(cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        with pytest.raises(PermissionError):
            _run(wm.get_frame())

    def test_get_frame_denied_even_with_cached_recent_frame(self, cfg):
        """The <2s cached-frame shortcut in get_frame() must not bypass
        the privacy check — a frame captured just before privacy was
        entered must not be handed out afterward."""
        import time
        wm = WebcamManager(cfg)
        wm._running = True
        wm._current_frame = b"stale-jpeg-bytes"
        wm._last_frame_time = time.monotonic()

        gate = get_privacy_gate(cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        with pytest.raises(PermissionError):
            _run(wm.get_frame())

    def test_get_frame_works_normally_without_privacy(self, cfg, monkeypatch):
        wm = WebcamManager(cfg)
        wm._running = True
        import time
        wm._current_frame = b"fresh-jpeg-bytes"
        wm._last_frame_time = time.monotonic()

        result = _run(wm.get_frame())
        assert result == b"fresh-jpeg-bytes"


class TestStreamFramesDeniedDuringPrivacy:
    def test_stream_frames_yields_nothing_when_privacy_active(self, cfg):
        wm = WebcamManager(cfg)
        wm._running = True
        gate = get_privacy_gate(cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        async def collect():
            frames = []
            async for f in wm.stream_frames():
                frames.append(f)
            return frames

        assert _run(collect()) == []

    def test_stream_frames_stops_if_privacy_entered_mid_stream(self, cfg):
        """Privacy entered while stream_frames() is waiting on the frame
        condition — must not yield the frame that arrives afterward."""
        wm = WebcamManager(cfg)
        wm._running = True
        gate = get_privacy_gate(cfg)

        async def scenario():
            frames = []

            async def enter_privacy_and_deliver_frame():
                await asyncio.sleep(0.01)
                gate.enter(PrivacyMode.PRIVACY, actor="test")
                wm._current_frame = b"frame-after-privacy"
                async with wm._frame_condition:
                    wm._frame_condition.notify_all()

            gen = wm.stream_frames()
            task = asyncio.create_task(enter_privacy_and_deliver_frame())
            async for f in gen:
                frames.append(f)
            await task
            return frames

        assert _run(scenario()) == []


class TestPrivacyFlushStopsRunningCapture:
    def test_flush_clears_current_frame(self, cfg):
        wm = WebcamManager(cfg)
        wm._current_frame = b"some-frame"
        wm._loop = None  # capture never actually started on a loop

        wm._privacy_flush()

        assert wm._current_frame is None

    def test_flush_stops_capture_running_on_its_loop(self, cfg):
        """The realistic case: a capture is running on WebcamManager's
        own asyncio loop (as it would via jarvis_continuous.py's
        dedicated async-loop thread), and gate.enter() — called from a
        different thread — must actually tear it down, not just flag it."""
        import threading

        wm = WebcamManager(cfg)
        stop_called = []

        async def fake_stop():
            stop_called.append(True)
            wm._running = False
            wm._current_frame = None

        wm.stop = fake_stop

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        try:
            wm._loop = loop
            wm._running = True
            wm._current_frame = b"live-frame"

            wm._privacy_flush()  # called synchronously, as PrivacyGate does

            assert stop_called == [True]
            assert wm._current_frame is None
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2)

    def test_gate_enter_triggers_flush_via_registered_callback(self, cfg):
        """End-to-end within this manager: enter() on the gate this
        WebcamManager registered with must reach _privacy_flush()."""
        wm = WebcamManager(cfg)
        wm._current_frame = b"some-frame"
        wm._loop = None

        gate = get_privacy_gate(cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        assert wm._current_frame is None
