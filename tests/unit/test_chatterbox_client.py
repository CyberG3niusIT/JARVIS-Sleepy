"""Unit tests for TextToSpeech's Chatterbox client-side health-check
throttling and cache-voice fingerprinting (core/tts.py). No network, no
GPU — urllib.request.urlopen is monkeypatched.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import core.tts as tts_module
from core.tts import TextToSpeech


class _NullLogger:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


def _make_tts():
    tts = TextToSpeech.__new__(TextToSpeech)
    tts.engine = "chatterbox"
    tts.chatterbox_endpoint = "http://127.0.0.1:8765/tts"
    tts.chatterbox_timeout = 60
    tts.logger = _NullLogger()
    tts._chatterbox_next_health_check = 0.0
    tts._chatterbox_last_health_ok = True
    return tts


class _FakeResponse:
    def __init__(self, status=200, body=b"{}"):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestHealthCheckThrottling:
    def test_down_server_fails_fast_not_after_full_timeout(self, monkeypatch):
        tts = _make_tts()
        calls = []

        def fake_urlopen(url, timeout=None):
            calls.append((url, timeout))
            raise OSError("connection refused")

        monkeypatch.setattr(tts_module.urllib.request, "urlopen", fake_urlopen)

        t0 = time.monotonic()
        available = tts._chatterbox_available()
        elapsed = time.monotonic() - t0

        assert available is False
        # Uses the short health-check timeout, never the full generation
        # timeout (60s) — this is what prevents a 60s hang before falling
        # back to Piper.
        assert calls[0][1] == TextToSpeech._CHATTERBOX_HEALTH_TIMEOUT
        assert elapsed < 2.0

    def test_healthy_result_is_throttled_not_rechecked_every_call(self, monkeypatch):
        tts = _make_tts()
        calls = []

        def fake_urlopen(url, timeout=None):
            calls.append(url)
            return _FakeResponse(status=200)

        monkeypatch.setattr(tts_module.urllib.request, "urlopen", fake_urlopen)

        for _ in range(5):
            assert tts._chatterbox_available() is True
        # Only the first call actually probed the network — the rest hit
        # the throttle window (_CHATTERBOX_HEALTH_RECHECK_OK).
        assert len(calls) == 1

    def test_recovery_is_rechecked_sooner_than_healthy_window(self, monkeypatch):
        tts = _make_tts()
        state = {"ok": False}

        def fake_urlopen(url, timeout=None):
            if state["ok"]:
                return _FakeResponse(status=200)
            raise OSError("down")

        monkeypatch.setattr(tts_module.urllib.request, "urlopen", fake_urlopen)

        assert tts._chatterbox_available() is False
        next_check_after_down = tts._chatterbox_next_health_check
        # Down re-check window must be shorter than the healthy one so a
        # server that comes back gets noticed quickly.
        assert (next_check_after_down - time.monotonic()) <= TextToSpeech._CHATTERBOX_HEALTH_RECHECK_DOWN + 0.1


class TestVoiceFingerprint:
    def test_fingerprint_changes_when_server_config_changes(self, monkeypatch):
        tts = _make_tts()

        configs = [
            {"exaggeration": 0.5, "cfg_weight": 0.5, "tempo": 0.89},
            {"exaggeration": 0.7, "cfg_weight": 0.5, "tempo": 0.89},
        ]

        def fake_urlopen(url, timeout=None):
            return _FakeResponse(body=json.dumps(configs.pop(0)).encode())

        monkeypatch.setattr(tts_module.urllib.request, "urlopen", fake_urlopen)

        fp1 = tts._chatterbox_voice_fingerprint()
        fp2 = tts._chatterbox_voice_fingerprint()
        assert fp1 != fp2

    def test_fingerprint_stable_for_same_config(self, monkeypatch):
        tts = _make_tts()
        cfg = {"exaggeration": 0.5, "cfg_weight": 0.5, "tempo": 0.89}

        def fake_urlopen(url, timeout=None):
            return _FakeResponse(body=json.dumps(cfg).encode())

        monkeypatch.setattr(tts_module.urllib.request, "urlopen", fake_urlopen)

        assert tts._chatterbox_voice_fingerprint() == tts._chatterbox_voice_fingerprint()

    def test_unreachable_server_falls_back_to_placeholder(self, monkeypatch):
        tts = _make_tts()

        def fake_urlopen(url, timeout=None):
            raise OSError("down")

        monkeypatch.setattr(tts_module.urllib.request, "urlopen", fake_urlopen)

        assert tts._chatterbox_voice_fingerprint() == "unknown"

    def test_cache_version_includes_engine_and_fingerprint(self, monkeypatch):
        tts = _make_tts()
        tts.config = {}

        def fake_urlopen(url, timeout=None):
            return _FakeResponse(body=b'{"a": 1}')

        monkeypatch.setattr(tts_module.urllib.request, "urlopen", fake_urlopen)

        version = tts._cache_voice_version()
        assert version.startswith(f"{TextToSpeech._CAL_L0_SCHEMA_VERSION}-chatterbox-")
        assert version != f"{TextToSpeech._CAL_L0_SCHEMA_VERSION}-chatterbox-unknown"
