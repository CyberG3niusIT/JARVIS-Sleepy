"""Unit tests for TTS startup warmup contention (docs/ARCHITECTURE.md §19
per the task numbering): ack cache and CAL-L0 cache used to warm up in
two parallel background threads, both hitting the single-threaded
Chatterbox server at once, risking a live speak() request queuing behind
a ~300-phrase warmup batch. Verifies the sequential-and-throttled fix.
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


def _make_tts():
    tts = TextToSpeech.__new__(TextToSpeech)
    tts.engine = "chatterbox"
    tts.logger = _NullLogger()
    tts._tts_lock = threading.Lock()
    return tts


class TestWarmupIsSequentialNotParallel:
    def test_run_chatterbox_warmup_calls_ack_before_cal_l0(self):
        tts = _make_tts()
        order = []
        tts._build_ack_cache = lambda: order.append("ack")
        tts._build_cal_l0_cache = lambda: order.append("cal_l0")

        tts._run_chatterbox_warmup()

        assert order == ["ack", "cal_l0"]


class TestAckCacheUsesThrottledSynthForChatterbox:
    """Reviewer-found gap: _build_ack_cache() called the unthrottled
    _synthesize_short_pcm even for Chatterbox, so the ~9 ack phrases hit
    the server with no _tts_lock protection at all — contrary to
    _run_chatterbox_warmup's documented intent that warmup never blocks
    a live request for more than one in-flight phrase."""

    def test_chatterbox_ack_cache_uses_throttled_synth(self, monkeypatch):
        tts = _make_tts()
        calls = {"throttled": 0, "unthrottled": 0}

        def fake_persona_pool_tagged(category):
            return [("Einen Moment.", "neutral")]

        monkeypatch.setattr("core.persona.pool_tagged", fake_persona_pool_tagged)

        def throttled(text):
            calls["throttled"] += 1
            return b"\x00\x00"

        def unthrottled(text):
            calls["unthrottled"] += 1
            return b"\x00\x00"

        tts._synthesize_short_pcm_throttled = throttled
        tts._synthesize_short_pcm = unthrottled
        tts._ack_cache = {}

        tts._build_ack_cache()

        assert calls["throttled"] == 1
        assert calls["unthrottled"] == 0

    def test_kokoro_ack_cache_uses_unthrottled_synth(self, monkeypatch):
        # Kokoro is in-process CPU — no shared server to contend over,
        # so it should keep using the plain (untimed) path.
        tts = TextToSpeech.__new__(TextToSpeech)
        tts.engine = "kokoro"
        tts.logger = _NullLogger()
        tts._tts_lock = threading.Lock()
        calls = {"throttled": 0, "unthrottled": 0}

        monkeypatch.setattr(
            "core.persona.pool_tagged",
            lambda category: [("One moment.", "neutral")],
        )
        tts._synthesize_short_pcm_throttled = lambda text: (_ for _ in ()).throw(
            AssertionError("kokoro must not use the throttled path")
        )
        tts._synthesize_short_pcm = lambda text: b"\x00\x00"
        tts._ack_cache = {}

        tts._build_ack_cache()  # must not raise


class TestThrottledSynthesisContendsForTtsLock:
    def test_throttled_synth_acquires_and_releases_lock_per_call(self):
        tts = _make_tts()
        lock_held_during_call = []

        def fake_synth(text):
            lock_held_during_call.append(tts._tts_lock.locked())
            return b"\x00\x00"

        tts._synthesize_short_pcm = fake_synth
        tts._synthesize_short_pcm_throttled("phrase 1")

        assert lock_held_during_call == [True]
        # Released afterward — a live request isn't blocked once this
        # single phrase is done.
        assert not tts._tts_lock.locked()

    def test_live_speak_can_interleave_between_warmup_phrases(self):
        """A live caller waiting on _tts_lock must be able to acquire it
        between two throttled warmup phrases, not just after the whole
        batch — this is what bounds live-request delay to "one phrase",
        not "the whole ~300-phrase warmup"."""
        tts = _make_tts()
        tts._synthesize_short_pcm = lambda text: b"\x00\x00"

        acquired_live = threading.Event()

        def live_request():
            # Wait for a gap between warmup phrases, then grab the lock
            # like a real speak() call would.
            time.sleep(0.05)
            with tts._tts_lock:
                acquired_live.set()

        t = threading.Thread(target=live_request, daemon=True)
        t.start()

        for _ in range(5):
            tts._synthesize_short_pcm_throttled("phrase")
            time.sleep(0.02)  # gap between phrases, like real HTTP latency

        t.join(timeout=2)
        assert acquired_live.is_set(), (
            "live request never got a chance to acquire _tts_lock between "
            "warmup phrases — throttling would be pointless if the lock "
            "were held for the whole batch instead of per-phrase"
        )
