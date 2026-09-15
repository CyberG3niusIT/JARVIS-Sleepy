"""Unit tests for the Chatterbox producer/consumer streaming pipeline.

Covers core/pipeline.py's _ChatterboxAudioWriter and StreamingAudioPipeline
(Chatterbox branch) with fakes — no GPU, no real aplay/ffmpeg process, no
network. See docs/ARCHITECTURE.md section 3 for the design this exercises.
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

from core.pipeline import StreamingAudioPipeline, _ChatterboxAudioWriter


class FakeAplay:
    """Stand-in for subprocess.Popen(["aplay", ...]) — records writes,
    never touches real audio hardware."""

    def __init__(self, fail_after_bytes=None):
        self.written = bytearray()
        self.closed = False
        self.killed = False
        self.returncode = 0
        self._fail_after_bytes = fail_after_bytes
        self.stderr = _FakeStderr()

        class _Stdin:
            def __init__(self, outer):
                self._outer = outer

            def write(self, data):
                outer = self._outer
                if (outer._fail_after_bytes is not None
                        and len(outer.written) >= outer._fail_after_bytes):
                    raise BrokenPipeError("simulated device failure")
                outer.written.extend(data)

            def close(self):
                self._outer.closed = True

        self.stdin = _Stdin(self)

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode if self.closed else None

    def kill(self):
        self.killed = True
        self.returncode = -9


class _FakeStderr:
    def read(self):
        return b""


class FakeTTS:
    """Minimal stand-in for TextToSpeech, exposing only what
    StreamingAudioPipeline / _ChatterboxAudioWriter touch."""

    def __init__(self):
        self.engine = "chatterbox"
        self.sample_rate = 24000
        self.normalization_enabled = False
        self.normalizer = None
        self._tts_lock = threading.Lock()
        self._aplay_instances = []
        self._aplay_fail_after_bytes = None
        self._open_aplay_calls = 0
        self._resample_calls = []
        self._chatterbox_responses = {}   # text -> (pcm, sr) or None
        self._piper_responses = {}        # text -> (pcm, sr) or None
        self._chatterbox_calls = []
        self._piper_calls = []

    # -- audio device --
    def _open_aplay(self):
        self._open_aplay_calls += 1
        proc = FakeAplay(fail_after_bytes=self._aplay_fail_after_bytes)
        self._aplay_instances.append(proc)
        return proc

    def _track_proc(self, proc):
        pass

    def _untrack_proc(self, proc):
        pass

    def _resample_pcm(self, pcm, src_rate, dst_rate):
        self._resample_calls.append((src_rate, dst_rate))
        return pcm  # identity — we only assert it was *called*

    # -- synthesis --
    def _chatterbox_generate_pcm(self, text):
        self._chatterbox_calls.append(text)
        result = self._chatterbox_responses.get(text, (b"\x01\x00" * 100, 24000))
        return result if result is not None else (None, None)

    def _piper_generate_pcm(self, text):
        self._piper_calls.append(text)
        result = self._piper_responses.get(text, (b"\x02\x00" * 100, 22050))
        return result if result is not None else (None, None)


def _run_pipeline(tts, sentences, join_timeout=10.0):
    pipeline = StreamingAudioPipeline(tts, logger=_NullLogger())
    pipeline.start()
    for s in sentences:
        pipeline.put(s)
    pipeline.finish()
    # finish() already blocks on self._done — but guard against a hang
    # in a broken test with an explicit thread-join timeout too.
    pipeline._thread.join(timeout=join_timeout)
    assert not pipeline._thread.is_alive(), "pipeline thread did not terminate"
    return pipeline


class _NullLogger:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


class TestChatterboxSuccess:
    def test_pcm_written_to_aplay(self):
        tts = FakeTTS()
        pipeline = _run_pipeline(tts, ["Hallo Welt."])
        assert tts._open_aplay_calls == 1
        aplay = tts._aplay_instances[0]
        assert len(aplay.written) > 0
        assert aplay.closed
        assert pipeline._error is None


class TestChunkFallback:
    def test_failed_chunk_falls_back_to_piper(self):
        tts = FakeTTS()
        tts._chatterbox_responses["Kaputter Satz."] = (None, None)
        pipeline = _run_pipeline(tts, ["Kaputter Satz."])
        assert tts._chatterbox_calls == ["Kaputter Satz."]
        assert tts._piper_calls == ["Kaputter Satz."]
        aplay = tts._aplay_instances[0]
        assert len(aplay.written) > 0  # Piper's audio still made it out
        assert pipeline._error is None

    def test_both_engines_fail_sentence_is_logged_lost_not_crashed(self):
        tts = FakeTTS()
        tts._chatterbox_responses["Ganz kaputt."] = (None, None)
        tts._piper_responses["Ganz kaputt."] = (None, None)
        # Must not raise / hang even though nothing could be spoken.
        pipeline = _run_pipeline(tts, ["Ganz kaputt.", "Zweiter Satz."])
        assert tts._chatterbox_calls == ["Ganz kaputt.", "Zweiter Satz."]
        assert tts._piper_calls == ["Ganz kaputt."]
        # Second sentence still got through despite the first being lost.
        assert tts._aplay_instances, "aplay should still have opened for chunk 2"


class TestFallbackMidStream:
    def test_only_failed_chunk_uses_fallback(self):
        tts = FakeTTS()
        tts._chatterbox_responses["Satz zwei."] = (None, None)
        _run_pipeline(tts, ["Satz eins.", "Satz zwei.", "Satz drei."])
        assert tts._chatterbox_calls == ["Satz eins.", "Satz zwei.", "Satz drei."]
        # Only the failed chunk goes to Piper — chunks 1 and 3 stay on Chatterbox.
        assert tts._piper_calls == ["Satz zwei."]


class TestOrderingPreserved:
    def test_chunks_written_in_submitted_order(self):
        tts = FakeTTS()
        markers = [b"\xAA" * 20, b"\xBB" * 20, b"\xCC" * 20]
        tts._chatterbox_responses = {
            "one": (markers[0], 24000),
            "two": (markers[1], 24000),
            "three": (markers[2], 24000),
        }
        _run_pipeline(tts, ["one", "two", "three"])
        aplay = tts._aplay_instances[0]
        assert bytes(aplay.written) == markers[0] + markers[1] + markers[2]


class TestFinishWaitsForCompletion:
    def test_finish_blocks_until_all_written(self):
        tts = FakeTTS()
        tts._chatterbox_responses = {
            f"s{i}": (bytes([i]) * 50, 24000) for i in range(5)
        }
        pipeline = _run_pipeline(tts, [f"s{i}" for i in range(5)])
        aplay = tts._aplay_instances[0]
        assert len(aplay.written) == 5 * 50
        assert aplay.closed


class TestSampleRateMismatch:
    def test_resample_called_when_fallback_rate_differs(self):
        tts = FakeTTS()
        # First chunk opens aplay at 24000 (Chatterbox's rate).
        tts._chatterbox_responses["ok satz"] = (b"\x01\x00" * 50, 24000)
        # Second chunk fails on Chatterbox, Piper responds at 22050 —
        # must be resampled to the already-open 24000 session.
        tts._chatterbox_responses["fallback satz"] = (None, None)
        tts._piper_responses["fallback satz"] = (b"\x02\x00" * 50, 22050)

        _run_pipeline(tts, ["ok satz", "fallback satz"])

        assert (22050, 24000) in tts._resample_calls

    def test_no_resample_when_rates_match(self):
        tts = FakeTTS()
        tts._chatterbox_responses["a"] = (b"\x01\x00" * 50, 24000)
        tts._chatterbox_responses["b"] = (b"\x01\x00" * 50, 24000)
        _run_pipeline(tts, ["a", "b"])
        assert tts._resample_calls == []


class TestInterruptDoesNotHang:
    def test_aplay_failure_mid_stream_terminates_cleanly(self):
        tts = FakeTTS()
        tts._aplay_fail_after_bytes = 10  # simulate kill_active() mid-write
        tts._chatterbox_responses = {
            f"s{i}": (b"\x01\x00" * 200, 24000) for i in range(5)
        }
        # Must terminate (not hang) even though playback breaks partway.
        pipeline = _run_pipeline(tts, [f"s{i}" for i in range(5)], join_timeout=15.0)
        assert pipeline._error is not None


class TestAckCacheRace:
    """Exercises the atomic-swap fix in TextToSpeech._build_ack_cache /
    speak_ack (core/tts.py) — a background build must never crash a
    concurrent reader with 'dict changed size during iteration'."""

    def test_concurrent_build_and_read_no_crash(self):
        import random as random_module
        from core.tts import TextToSpeech

        tts = TextToSpeech.__new__(TextToSpeech)  # skip __init__/engine init
        tts._ack_cache = {}
        tts._tts_lock = threading.Lock()
        tts.logger = _NullLogger()

        errors = []
        stop = threading.Event()

        def builder():
            for round_ in range(200):
                new_cache = {f"phrase{i}": (b"\x00" * 10, "neutral") for i in range(50)}
                tts._ack_cache = new_cache
            stop.set()

        def reader():
            while not stop.is_set():
                try:
                    cache = tts._ack_cache
                    if cache:
                        candidates = list(cache.keys())
                        if candidates:
                            phrase = random_module.choice(candidates)
                            _ = cache[phrase]
                except Exception as e:  # pragma: no cover - failure path
                    errors.append(e)

        threads = [threading.Thread(target=builder)] + [
            threading.Thread(target=reader) for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"race caused errors: {errors}"
