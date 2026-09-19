"""Unit tests for the contextual-ack/TTS-lock race (core/tts.py speak()
cancel_check + timeout_override; wired from core/pipeline.py's
_play_ack_if_still_thinking).

Bug: a dynamically-generated contextual ack went through the same
speak() a real response uses. For Chatterbox that is a real GPU
synthesis HTTP request that holds _tts_lock for up to the full
response-length timeout, with no cancellation once started — so a
slow/large ack could delay the real first response chunk by far more
than the ack itself was worth. speak() now takes an optional
cancel_check (re-checked immediately after lock acquisition, mirroring
the existing speak_ack() pattern) and a timeout_override that caps the
Chatterbox request specifically for that call.
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

from core.tts import TextToSpeech


class _NullLogger:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


def _make_tts(engine="chatterbox"):
    tts = TextToSpeech.__new__(TextToSpeech)
    tts.engine = engine
    tts.logger = _NullLogger()
    tts._tts_lock = threading.Lock()
    tts._spoke = False
    tts._tts_cache = {}
    tts.normalization_enabled = False
    tts.normalizer = None
    return tts


class TestCancelCheckAfterLockAcquisition:
    def test_cancel_check_true_aborts_before_synthesis(self):
        tts = _make_tts()
        tts._speak_chatterbox = lambda text, timeout_override=None: (
            (_ for _ in ()).throw(AssertionError("must not synthesize when cancelled"))
        )

        result = tts.speak("Einen Moment.", cancel_check=lambda: True)

        assert result is False

    def test_cancel_check_false_proceeds_to_synthesis(self):
        tts = _make_tts()
        calls = []
        tts._speak_chatterbox = lambda text, timeout_override=None: (
            calls.append((text, timeout_override)) or True
        )

        result = tts.speak("Einen Moment.", cancel_check=lambda: False)

        assert result is True
        assert calls == [("Einen Moment.", None)]

    def test_no_cancel_check_behaves_as_before(self):
        tts = _make_tts()
        tts._speak_chatterbox = lambda text, timeout_override=None: True
        assert tts.speak("hallo") is True

    def test_cancel_check_raced_against_response_flag(self):
        """Simulates the real scenario: cancel_check reads a mutable flag
        that flips to True (real response arrived) between the ack being
        triggered and the lock actually being acquired."""
        tts = _make_tts()
        llm_responded = {"flag": False}
        tts._speak_chatterbox = lambda text, timeout_override=None: (
            (_ for _ in ()).throw(AssertionError("must not synthesize — response already arrived"))
        )

        # Flip the flag as if the real response beat the ack to the lock.
        llm_responded["flag"] = True

        result = tts.speak("Einen Moment.", cancel_check=lambda: llm_responded["flag"])
        assert result is False


class TestTimeoutOverridePassedToChatterbox:
    def test_timeout_override_forwarded_to_speak_chatterbox(self):
        tts = _make_tts()
        captured = {}

        def fake_speak_chatterbox(text, timeout_override=None):
            captured["timeout_override"] = timeout_override
            return True

        tts._speak_chatterbox = fake_speak_chatterbox
        tts.speak("Einen Moment.", timeout_override=2.5)

        assert captured["timeout_override"] == 2.5

    def test_speak_chatterbox_uses_override_instead_of_configured_timeout(self):
        tts = _make_tts()
        tts.chatterbox_timeout = 30  # a real response's generous budget
        tts.chatterbox_connect_timeout = 1
        tts.chatterbox_endpoint = "http://127.0.0.1:8765/tts"

        captured_timeouts = []

        class _FakeResponse:
            content = b"NOTRIFF"  # fails the RIFF check — short-circuits before aplay

        class _FakeSession:
            def post(self, url, json, timeout):
                captured_timeouts.append(timeout)
                return _FakeResponse()

        tts._chatterbox_session = _FakeSession()
        tts._chatterbox_available = lambda: True
        tts._chatterbox_record_failure = lambda: None

        tts._speak_chatterbox("Einen Moment.", timeout_override=2.5)

        assert captured_timeouts == [(1, 2.5)]  # NOT (1, 30) — the configured full timeout

    def test_speak_chatterbox_falls_back_to_configured_timeout_when_no_override(self):
        tts = _make_tts()
        tts.chatterbox_timeout = 30
        tts.chatterbox_connect_timeout = 1
        tts.chatterbox_endpoint = "http://127.0.0.1:8765/tts"

        captured_timeouts = []

        class _FakeResponse:
            content = b"NOTRIFF"

        class _FakeSession:
            def post(self, url, json, timeout):
                captured_timeouts.append(timeout)
                return _FakeResponse()

        tts._chatterbox_session = _FakeSession()
        tts._chatterbox_available = lambda: True
        tts._chatterbox_record_failure = lambda: None

        tts._speak_chatterbox("Ein regulaerer Antworttext.")

        assert captured_timeouts == [(1, 30)]


class TestAckNeverOutlivesRealResponseLock:
    """End-to-end-ish: a slow ack synthesis (simulated) must release the
    lock within its bounded timeout, not the real response's timeout,
    so the real response's speak() call is never blocked longer than
    that bound."""

    def test_real_response_acquires_lock_promptly_after_bounded_ack(self):
        tts = _make_tts()
        ack_duration = 0.05

        def slow_ack_synth(text, timeout_override=None):
            # Simulates a bounded Chatterbox call respecting timeout_override
            # by finishing within it (the real HTTP client would raise
            # requests.Timeout instead; either way _tts_lock is released
            # promptly because the call itself is bounded).
            time.sleep(ack_duration)
            return True

        tts._speak_chatterbox = slow_ack_synth

        real_response_got_lock_at = []
        start = time.monotonic()

        def real_response():
            tts.speak("Die eigentliche Antwort.")
            real_response_got_lock_at.append(time.monotonic() - start)

        ack_thread = threading.Thread(
            target=lambda: tts.speak(
                "Einen Moment.", cancel_check=lambda: False, timeout_override=ack_duration * 2,
            )
        )
        ack_thread.start()
        time.sleep(0.01)  # let the ack grab the lock first
        real_thread = threading.Thread(target=real_response)
        real_thread.start()

        ack_thread.join(timeout=2)
        real_thread.join(timeout=2)

        assert real_response_got_lock_at
        # Bounded by the ack's own (short) duration, not some large
        # unrelated real-response timeout.
        assert real_response_got_lock_at[0] < 1.0
