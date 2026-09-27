"""Unit tests for TextToSpeech's Chatterbox client-side health-check
throttling, circuit breaker, and cache-voice fingerprinting
(core/tts.py). No real network, no GPU — the requests.Session used for
all Chatterbox HTTP calls is replaced with a fake.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

from core.tts import TextToSpeech


class _NullLogger:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None, content=b""):
        self.status_code = status_code
        self._json_body = json_body
        self.content = content

    def json(self):
        return self._json_body


class _FakeSession:
    """Stand-in for requests.Session — records calls, raises/returns
    whatever the test configures."""

    def __init__(self, get_fn=None, post_fn=None):
        self.get_calls = []
        self.post_calls = []
        self._get_fn = get_fn or (lambda url, timeout=None: _FakeResponse())
        self._post_fn = post_fn or (lambda url, json=None, timeout=None: _FakeResponse())

    def get(self, url, timeout=None):
        self.get_calls.append((url, timeout))
        return self._get_fn(url, timeout=timeout)

    def post(self, url, json=None, timeout=None):
        self.post_calls.append((url, json, timeout))
        return self._post_fn(url, json=json, timeout=timeout)


def _make_tts(session=None):
    tts = TextToSpeech.__new__(TextToSpeech)
    tts.engine = "chatterbox"
    tts.chatterbox_endpoint = "http://127.0.0.1:8765/tts"
    tts.chatterbox_timeout = 60
    tts.chatterbox_connect_timeout = 2.0
    tts.logger = _NullLogger()
    tts._chatterbox_session = session or _FakeSession()
    tts._chatterbox_next_health_check = 0.0
    tts._chatterbox_last_health_ok = True
    tts._chatterbox_consecutive_failures = 0
    tts._chatterbox_circuit_open_until = 0.0
    return tts


class TestHealthCheckThrottling:
    def test_down_server_fails_fast_not_after_full_timeout(self):
        def failing_get(url, timeout=None):
            raise OSError("connection refused")

        tts = _make_tts(_FakeSession(get_fn=failing_get))

        t0 = time.monotonic()
        available = tts._chatterbox_available()
        elapsed = time.monotonic() - t0

        assert available is False
        # Uses the short health-check timeout (as the read half of the
        # connect/read tuple), never the full generation timeout (60s) —
        # this is what prevents a 60s hang before falling back to Piper.
        called_timeout = tts._chatterbox_session.get_calls[0][1]
        assert called_timeout == (tts.chatterbox_connect_timeout, TextToSpeech._CHATTERBOX_HEALTH_TIMEOUT)
        assert elapsed < 2.0

    def test_healthy_result_is_throttled_not_rechecked_every_call(self):
        tts = _make_tts()

        for _ in range(5):
            assert tts._chatterbox_available() is True
        # Only the first call actually probed the network — the rest hit
        # the throttle window (_CHATTERBOX_HEALTH_RECHECK_OK).
        assert len(tts._chatterbox_session.get_calls) == 1

    def test_recovery_is_rechecked_sooner_than_healthy_window(self):
        def failing_get(url, timeout=None):
            raise OSError("down")

        tts = _make_tts(_FakeSession(get_fn=failing_get))

        assert tts._chatterbox_available() is False
        next_check_after_down = tts._chatterbox_next_health_check
        # Down re-check window must be shorter than the healthy one so a
        # server that comes back gets noticed quickly.
        assert (next_check_after_down - time.monotonic()) <= TextToSpeech._CHATTERBOX_HEALTH_RECHECK_DOWN + 0.1


class TestCircuitBreaker:
    def test_opens_after_consecutive_failures(self):
        tts = _make_tts()
        for _ in range(TextToSpeech._CHATTERBOX_CIRCUIT_FAILURE_THRESHOLD):
            tts._chatterbox_record_failure()
        assert tts._chatterbox_circuit_open() is True

    def test_stays_closed_below_threshold(self):
        tts = _make_tts()
        for _ in range(TextToSpeech._CHATTERBOX_CIRCUIT_FAILURE_THRESHOLD - 1):
            tts._chatterbox_record_failure()
        assert tts._chatterbox_circuit_open() is False

    def test_success_resets_failure_count(self):
        tts = _make_tts()
        tts._chatterbox_record_failure()
        tts._chatterbox_record_failure()
        tts._chatterbox_record_success()
        assert tts._chatterbox_consecutive_failures == 0
        assert tts._chatterbox_circuit_open() is False

    def test_open_circuit_short_circuits_available_without_health_probe(self):
        tts = _make_tts()
        for _ in range(TextToSpeech._CHATTERBOX_CIRCUIT_FAILURE_THRESHOLD):
            tts._chatterbox_record_failure()

        assert tts._chatterbox_available() is False
        # Circuit open means we don't even bother with a /health GET.
        assert tts._chatterbox_session.get_calls == []

    def test_generate_pcm_failure_opens_circuit(self):
        def failing_post(url, json=None, timeout=None):
            raise OSError("generation failed")

        tts = _make_tts(_FakeSession(post_fn=failing_post))
        for _ in range(TextToSpeech._CHATTERBOX_CIRCUIT_FAILURE_THRESHOLD):
            pcm, sr = tts._chatterbox_generate_pcm("Hallo")
            assert pcm is None

        assert tts._chatterbox_circuit_open() is True

    def test_generate_pcm_success_keeps_circuit_closed(self):
        import wave
        import io as io_module

        buf = io_module.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00\x00" * 100)
        wav_bytes = buf.getvalue()

        def ok_post(url, json=None, timeout=None):
            return _FakeResponse(content=wav_bytes)

        tts = _make_tts(_FakeSession(post_fn=ok_post))
        pcm, sr = tts._chatterbox_generate_pcm("Hallo")
        assert pcm is not None
        assert sr == 24000
        assert tts._chatterbox_consecutive_failures == 0


class TestConnectionReuse:
    def test_single_session_reused_across_requests(self):
        """The same requests.Session (hence its connection pool) must be
        reused across calls, not recreated per request."""
        import wave
        import io as io_module

        buf = io_module.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00\x00" * 10)
        wav_bytes = buf.getvalue()

        session = _FakeSession(post_fn=lambda url, json=None, timeout=None: _FakeResponse(content=wav_bytes))
        tts = _make_tts(session)

        for i in range(3):
            tts._chatterbox_generate_pcm(f"Satz {i}")

        assert len(session.post_calls) == 3
        # Same session object handled every call.
        assert tts._chatterbox_session is session

    def test_separate_connect_and_read_timeout_passed(self):
        import wave
        import io as io_module

        buf = io_module.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00\x00" * 10)
        wav_bytes = buf.getvalue()

        session = _FakeSession(post_fn=lambda url, json=None, timeout=None: _FakeResponse(content=wav_bytes))
        tts = _make_tts(session)
        tts.chatterbox_connect_timeout = 2.5
        tts.chatterbox_timeout = 45

        tts._chatterbox_generate_pcm("Hallo")

        _, _, timeout = session.post_calls[0]
        assert timeout == (2.5, 45)


class TestVoiceFingerprint:
    def test_fingerprint_changes_when_server_config_changes(self):
        configs = [
            {"exaggeration": 0.5, "cfg_weight": 0.5, "tempo": 0.89},
            {"exaggeration": 0.7, "cfg_weight": 0.5, "tempo": 0.89},
        ]

        def fake_get(url, timeout=None):
            return _FakeResponse(json_body=configs.pop(0))

        tts = _make_tts(_FakeSession(get_fn=fake_get))

        fp1 = tts._chatterbox_voice_fingerprint()
        fp2 = tts._chatterbox_voice_fingerprint()
        assert fp1 != fp2

    def test_fingerprint_stable_for_same_config(self):
        cfg = {"exaggeration": 0.5, "cfg_weight": 0.5, "tempo": 0.89}
        tts = _make_tts(_FakeSession(get_fn=lambda url, timeout=None: _FakeResponse(json_body=cfg)))

        assert tts._chatterbox_voice_fingerprint() == tts._chatterbox_voice_fingerprint()

    def test_unreachable_server_falls_back_to_placeholder(self):
        def failing_get(url, timeout=None):
            raise OSError("down")

        tts = _make_tts(_FakeSession(get_fn=failing_get))
        assert tts._chatterbox_voice_fingerprint() == "unknown"

    def test_cache_version_includes_engine_and_fingerprint(self):
        tts = _make_tts(_FakeSession(get_fn=lambda url, timeout=None: _FakeResponse(json_body={"a": 1})))
        tts.config = {}

        version = tts._cache_voice_version()
        assert version.startswith(f"{TextToSpeech._CAL_L0_SCHEMA_VERSION}-chatterbox-")
        assert version != f"{TextToSpeech._CAL_L0_SCHEMA_VERSION}-chatterbox-unknown"
