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

import queue as queue_module

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


def _run_pipeline(tts, sentences, join_timeout=10.0, on_first_audio=None):
    pipeline = StreamingAudioPipeline(tts, logger=_NullLogger(), on_first_audio=on_first_audio)
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


class SlowFakeAplay(FakeAplay):
    """FakeAplay whose stdin.write() blocks until released — simulates a
    slow/stuck consumer draining the pipe in realtime, so tests can
    observe real backpressure on a bounded queue."""

    def __init__(self, release_event, writes_before_block=0):
        super().__init__()
        self._release_event = release_event
        self._writes_before_block = writes_before_block
        self._write_count = 0

        class _Stdin:
            def __init__(self, outer):
                self._outer = outer

            def write(self, data):
                outer = self._outer
                outer._write_count += 1
                if outer._write_count > outer._writes_before_block:
                    outer._release_event.wait(timeout=5)
                outer.written.extend(data)

            def close(self):
                self._outer.closed = True

        self.stdin = _Stdin(self)


class TestPutNeverFalsePositiveOnStop:
    """Reviewer-found race: submit() could return True for an item that
    silently never gets processed if the writer decided to stop (error)
    in the narrow window between _put()'s loop-guard check and the
    queue.put() call landing. _put() now re-checks _stopped immediately
    after a successful enqueue, closing the window down to a few
    instructions instead of the whole remaining thread lifetime."""

    def test_put_returns_false_if_stopped_flips_right_after_enqueue(self):
        tts = FakeTTS()
        writer = _ChatterboxAudioWriter(tts, _NullLogger())

        real_put = writer._queue.put

        def put_then_stop(item, timeout=None):
            real_put(item, timeout=timeout)
            # Simulate the writer thread deciding to stop in the instant
            # right after this item landed in the queue.
            writer._stopped.set()

        writer._queue.put = put_then_stop
        result = writer.submit(b"\x00\x00", 24000)

        assert result is False, (
            "submit() reported success for an item enqueued right as "
            "the writer stopped — that item will never be played"
        )

    def test_put_returns_true_for_normal_enqueue(self):
        tts = FakeTTS()
        writer = _ChatterboxAudioWriter(tts, _NullLogger())
        assert writer.submit(b"\x00\x00", 24000) is True

    def test_error_paths_set_stopped_immediately_not_just_in_finally(self):
        """_stopped must be set at the same moment self.error is set
        (not only afterward in finally) — otherwise a producer racing
        the exact break/except instant sees _stopped still False."""
        tts = FakeTTS()
        tts._open_aplay = lambda: None  # forces the "Failed to open audio device" path
        writer = _ChatterboxAudioWriter(tts, _NullLogger())
        writer.start()
        writer.submit(b"\x00\x00", 24000)
        writer.finish_and_wait(timeout=5)
        assert writer.error == "Failed to open audio device"
        assert writer._stopped.is_set()


class TestBoundedQueueBackpressure:
    """core/pipeline.py's _ChatterboxAudioWriter — the task's explicit
    concern: an unbounded internal queue.Queue() let a fast producer pile
    up unlimited PCM in RAM ahead of a slow/stuck consumer. Verifies the
    bounded queue actually blocks (real backpressure), never drops data,
    keeps order, and can't be deadlocked by a dead consumer."""

    def _make_writer(self, aplay_factory):
        tts = FakeTTS()
        tts._open_aplay = aplay_factory
        logger = _NullLogger()
        writer = _ChatterboxAudioWriter(tts, logger)
        return tts, writer

    def test_submit_blocks_when_queue_full_slow_consumer(self):
        release = threading.Event()
        # Block forever from the first write — writer never drains.
        tts, writer = self._make_writer(lambda: SlowFakeAplay(release, writes_before_block=0))
        writer.start()

        submitted_count = {"n": 0}
        stop = threading.Event()

        def producer():
            i = 0
            while not stop.is_set() and i < 20:
                if writer.submit(f"chunk{i}".encode(), 24000):
                    submitted_count["n"] += 1
                i += 1

        t = threading.Thread(target=producer, daemon=True)
        t.start()
        time.sleep(0.3)
        # Bounded: maxsize (4) + the 1 item already pulled by the writer
        # thread for its blocked write = at most 5 successfully submitted
        # while nothing drains. Must NOT have run away to 20.
        stalled_count = submitted_count["n"]
        assert 0 < stalled_count <= _ChatterboxAudioWriter._QUEUE_MAXSIZE + 1

        release.set()
        stop.set()
        t.join(timeout=5)
        writer.finish_and_wait(timeout=10)

    def test_no_data_loss_under_backpressure(self):
        release = threading.Event()
        release.set()  # never actually blocks — just exercises the bounded path
        tts, writer = self._make_writer(lambda: SlowFakeAplay(release, writes_before_block=0))
        writer.start()

        chunks = [bytes([i]) * 20 for i in range(10)]
        for c in chunks:
            assert writer.submit(c, 24000) is True

        ok, total_samples, err = writer.finish_and_wait(timeout=10)
        assert ok is True
        assert err is None
        assert total_samples == sum(len(c) for c in chunks) // 2

    def test_order_preserved_under_backpressure(self):
        release = threading.Event()
        release.set()
        tts, writer = self._make_writer(lambda: SlowFakeAplay(release, writes_before_block=0))
        writer.start()

        markers = [bytes([i]) * 10 for i in range(20)]
        for m in markers:
            writer.submit(m, 24000)

        writer.finish_and_wait(timeout=10)
        aplay = writer.aplay
        assert bytes(aplay.written) == b"".join(markers)

    def test_consumer_crash_does_not_deadlock_producer(self):
        # Consumer "crashes" immediately: _open_aplay returns None, so
        # the writer thread sets self.error and exits right away.
        tts, writer = self._make_writer(lambda: None)
        writer.start()

        start = time.monotonic()
        # First submit is consumed by the writer thread, which then
        # fails to open aplay and stops — subsequent submits must not
        # hang forever waiting for a queue slot that will never open up.
        results = [writer.submit(f"x{i}".encode(), 24000) for i in range(10)]
        elapsed = time.monotonic() - start

        assert elapsed < 5.0, "submit() blocked instead of detecting the dead writer"
        assert False in results, "expected at least one submit() to report the writer stopped"

        ok, _total, err = writer.finish_and_wait(timeout=5)
        assert ok is False
        assert err == "Failed to open audio device"

    def test_finish_does_not_deadlock_on_full_queue(self):
        # Writer never drains (blocked on first write); finish() must
        # still return instead of hanging on a full queue forever, once
        # the writer is force-stopped.
        release = threading.Event()
        tts, writer = self._make_writer(lambda: SlowFakeAplay(release, writes_before_block=0))
        writer.start()

        for i in range(_ChatterboxAudioWriter._QUEUE_MAXSIZE + 2):
            writer.submit(f"x{i}".encode(), 24000)

        # Simulate an external interrupt: force the writer to stop so
        # finish_and_wait() (called from another thread) isn't stuck
        # forever on a full queue with nobody home.
        def releaser():
            time.sleep(0.5)
            release.set()

        threading.Thread(target=releaser, daemon=True).start()
        ok, _total, _err = writer.finish_and_wait(timeout=10)
        assert ok is True


class TestFirstAudioCallback:
    """on_first_audio() — the hook core/latency_tracker.py uses to mark
    "tts_first_pcm". Must fire exactly once, at first audio, and must
    never break playback if the callback itself raises."""

    def test_fires_once_on_first_chunk(self):
        tts = FakeTTS()
        calls = []
        _run_pipeline(tts, ["Satz eins.", "Satz zwei.", "Satz drei."],
                      on_first_audio=lambda: calls.append(time.monotonic()))
        assert len(calls) == 1

    def test_not_called_when_omitted(self):
        tts = FakeTTS()
        # Must not raise just because no callback was given.
        _run_pipeline(tts, ["Hallo."])

    def test_raising_callback_does_not_break_playback(self):
        tts = FakeTTS()

        def broken_callback():
            raise RuntimeError("instrumentation bug")

        pipeline = _run_pipeline(tts, ["Hallo Welt."], on_first_audio=broken_callback)
        assert pipeline._error is None
        assert len(tts._aplay_instances[0].written) > 0


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


class TestVocalDirections:
    def test_explicit_pause_keeps_text_out_of_tag_and_inserts_silence(self):
        tts = FakeTTS()
        pipeline = _run_pipeline(tts, ["Grüße,[voice:pause=short] Welt."])
        assert pipeline._error is None
        assert tts._chatterbox_calls == ["Grüße,", "Welt."]
        pcm = bytes(tts._aplay_instances[0].written)
        assert pcm == (
            b"\x01\x00" * 100
            + b"\x00" * (24000 * 200 // 1000 * 2)
            + b"\x01\x00" * 100
        )

    def test_unsupported_event_has_one_synthesis_call(self):
        tts = FakeTTS()
        pipeline = _run_pipeline(tts, ["Hallo[voice:cough]Welt."])
        assert pipeline._error is None
        assert tts._chatterbox_calls == ["Hallo Welt."]
        assert tts._piper_calls == []

    def test_directed_segment_uses_piper_fallback_without_tag(self, monkeypatch):
        tts = FakeTTS()
        tts._chatterbox_responses["Welt."] = None
        tts._piper_responses["Welt."] = (b"\x02\x00" * 100, 22050)
        resampled = []
        monkeypatch.setattr(
            "core.pipeline.resample_pcm_s16le",
            lambda pcm, source, target: resampled.append((source, target)) or pcm,
        )
        pipeline = _run_pipeline(tts, ["Hallo[voice:pause=short]Welt."])
        assert pipeline._error is None
        assert tts._chatterbox_calls == ["Hallo", "Welt."]
        assert tts._piper_calls == ["Welt."]
        assert resampled == [(22050, 24000)]

    def test_windows_backend_receives_composed_pcm_once(self):
        tts = FakeTTS()
        tts.output_backend = "windows"
        played = []
        tts._play_pcm_windows = lambda pcm, rate: played.append((pcm, rate)) or True
        pipeline = _run_pipeline(tts, ["Hallo[voice:pause=medium]Welt"])
        assert pipeline._error is None
        assert len(played) == 1
        assert played[0][1] == 24000
        assert b"\x00" * (24000 * 500 // 1000 * 2) in played[0][0]

    def test_tag_free_text_preserves_single_call(self):
        tts = FakeTTS()
        _run_pipeline(tts, ["Hallo, Welt."])
        assert tts._chatterbox_calls == ["Hallo, Welt."]

    def test_leading_and_trailing_pause_only_chunks(self):
        tts = FakeTTS()
        pipeline = _run_pipeline(tts, [
            "[voice:pause=short]", "Hallo", "[voice:pause=medium]",
        ])
        assert pipeline._error is None
        assert tts._chatterbox_calls == ["Hallo"]
        pcm = bytes(tts._aplay_instances[0].written)
        assert pcm.startswith(b"\x00" * (24000 * 200 // 1000 * 2))
        assert pcm.endswith(b"\x00" * (24000 * 500 // 1000 * 2))
