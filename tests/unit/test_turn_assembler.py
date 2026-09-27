"""Tests for natural utterance aggregation (core/turn_assembler.py) and its
ContinuousListener integration (sounddevice is stubbed)."""

import os
import queue
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import numpy as np
import pytest

from core.turn_assembler import TurnAssembler

SR = 16000


def seg(seconds, val=0.1):
    return np.full(int(seconds * SR), val, dtype=np.float32)


def asm(**kw):
    args = dict(grace_s=1.2, max_turn_s=20, max_segments=8, sample_rate=SR)
    args.update(kw)
    return TurnAssembler(**args)


class TestAggregation:
    def test_three_segments_within_grace_merge(self):
        a = asm()
        assert a.add(seg(3), 1, False, now=10.0) == []
        assert a.poll(now=10.5) is None
        assert a.add(seg(3), 1, False, now=11.0) == []
        assert a.add(seg(3), 1, False, now=12.0) == []
        assert a.poll(now=13.0) is None            # 1.0 s < grace
        turn = a.poll(now=13.3)                    # 1.3 s >= grace
        assert turn["audio"].shape[0] == 9 * SR
        assert turn["segments"] == 3
        assert turn["capture_generation"] == 1
        assert turn["during_tts"] is False
        assert a.pending == 0

    def test_pause_longer_than_grace_gives_two_turns(self):
        a = asm()
        a.add(seg(3), 1, False, now=10.0)
        t1 = a.poll(now=11.5)
        a.add(seg(3), 1, False, now=12.0)
        t2 = a.poll(now=13.5)
        assert t1["segments"] == 1 and t2["segments"] == 1
        assert t1["turn_id"] != t2["turn_id"]

    def test_max_turn_s_cap_by_audio(self):
        a = asm(max_turn_s=10)
        assert a.add(seg(4), 1, False, now=0.0) == []
        assert a.add(seg(4), 1, False, now=0.5) == []
        out = a.add(seg(4), 1, False, now=1.0)     # 12 s >= cap
        assert len(out) == 1 and out[0]["audio"].shape[0] == 12 * SR
        assert a.pending == 0

    def test_max_turn_s_cap_by_wall_clock(self):
        a = asm(max_turn_s=5, grace_s=100)
        a.add(seg(3), 1, False, now=0.0)
        assert a.poll(now=4.0) is None
        assert a.poll(now=5.0) is not None

    def test_max_segments_cap(self):
        a = asm(max_segments=3)
        assert a.add(seg(3), 1, False, now=0.0) == []
        assert a.add(seg(3), 1, False, now=0.1) == []
        out = a.add(seg(3), 1, False, now=0.2)
        assert len(out) == 1 and out[0]["segments"] == 3

    def test_noise_cannot_aggregate_unboundedly(self):
        a = asm(max_segments=4, max_turn_s=20)
        released = 0
        for i in range(40):
            released += len(a.add(seg(3), 1, False, now=i * 0.5))
            assert a.pending <= 4
        assert released == 10


class TestBypassAndDrop:
    def test_during_tts_not_merged(self):
        a = asm()
        a.add(seg(3), 1, False, now=0.0)
        out = a.add(seg(3), 1, True, now=0.5)
        assert len(out) == 1
        assert out[0]["during_tts"] is True and out[0]["segments"] == 1
        assert out[0]["audio"].shape[0] == 3 * SR
        assert a.pending == 1                      # held buffer untouched

    def test_stale_generation_dropped(self):
        a = asm()
        a.add(seg(3), 1, False, now=0.0)
        a.add(seg(3), 2, False, now=0.5)
        turn = a.poll(now=5.0)
        assert turn["capture_generation"] == 2
        assert turn["audio"].shape[0] == 3 * SR    # gen-1 audio not merged

    def test_clear_and_flush_drop_buffer(self):
        for method in ("clear", "flush", "discard"):
            a = asm()
            a.add(seg(3), 1, False, now=0.0)
            getattr(a, method)()
            assert a.pending == 0
            assert a.poll(now=100.0) is None

    def test_min_segment_ignored(self):
        a = asm(min_segment_s=1.0, fast_stop_max_s=0)
        assert a.add(seg(0.5), 1, False, now=0.0) == []
        assert a.pending == 0


class TestFastStop:
    def test_short_segment_released_immediately(self):
        a = asm()
        out = a.add(seg(1.0), 1, False, now=0.0)
        assert len(out) == 1
        assert out[0]["fast_stop_candidate"] is True
        assert a.pending == 0

    def test_short_continuation_is_merged_into_held_turn(self):
        # "Aura, Anna ist doppelt so alt wie Ben." + short follow-up sentences
        a = asm()
        assert a.add(seg(4), 1, False, now=0.0) == []
        assert a.add(seg(1.0), 1, False, now=0.5) == []
        assert a.pending == 2
        turn = a.poll(now=99)
        assert turn["audio"].shape[0] >= 5 * SR
        assert turn["fast_stop_candidate"] is False

    def test_discard_after_stop_match(self):
        a = asm()
        a.add(seg(4), 1, False, now=0.0)
        a.discard()
        assert a.poll(now=99) is None


# ------------------------------------------------------------- listener level
@pytest.fixture
def listener(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", types.ModuleType("sounddevice"))
    sys.modules.pop("core.continuous_listener", None)
    from core import privacy_gate
    privacy_gate.reset_privacy_gate_singleton_for_tests()
    from core.continuous_listener import ContinuousListener

    class Cfg(dict):
        def get(self, path, default=None):
            d = self
            for p in path.split("."):
                if isinstance(d, dict) and p in d:
                    d = d[p]
                else:
                    return default
            return d

    cfg = Cfg({"vad": {"aggressiveness": 2, "buffer_duration": 1.0},
               "turn": {"enabled": True, "grace_ms": 50}})
    q = queue.Queue()
    lst = ContinuousListener(cfg, stt=None, on_command=lambda *_: None, audio_queue=q)
    yield lst, q
    lst._turn_thread_stop.set()
    privacy_gate.reset_privacy_gate_singleton_for_tests()


def test_listener_release_has_legacy_shape(listener):
    lst, q = listener
    lst._submit_segment(seg(3), lst._capture_generation, False)
    lst._submit_segment(seg(3), lst._capture_generation, False)
    item = q.get(timeout=3)
    assert {"audio", "capture_generation", "during_tts"} <= set(item)
    assert item["audio"].shape[0] == 6 * SR + int(0.15 * SR)   # one turn.gap_s gap
    assert item["during_tts"] is False


def test_listener_privacy_flush_clears_assembler(listener):
    lst, q = listener
    lst._turn_assembler.grace_s = 100
    lst._submit_segment(seg(3), lst._capture_generation, False)
    assert lst._turn_assembler.pending == 1
    lst._privacy_flush_speech_buffer()
    assert lst._turn_assembler.pending == 0
    assert q.empty()


def test_listener_pause_and_resume_clear_assembler(listener):
    lst, q = listener
    lst._turn_assembler.grace_s = 100
    lst._submit_segment(seg(3), lst._capture_generation, False)
    lst.pause_listening()
    assert lst._turn_assembler.pending == 0
    lst._submit_segment(seg(3), lst._capture_generation, False)
    lst.invalidate_pending_audio()
    assert lst._turn_assembler.pending == 0


def test_listener_disabled_is_legacy(listener):
    lst, q = listener
    lst._turn_assembler = None
    lst._submit_segment(seg(3), 7, False)
    item = q.get_nowait()
    assert set(item) == {"audio", "capture_generation", "during_tts"}
    assert item["capture_generation"] == 7


# ------------------------------------------------ audit fixes (A2)
def test_add_speech_duration_drives_fast_stop():
    a = asm()
    # 2.8 s audio = 1.0 s pre-roll + 1.0 s "Stopp" + 0.8 s trailing silence
    out = a.add(seg(2.8), 1, False, now=0.0, speech_duration_s=1.0)
    assert len(out) == 1 and out[0]["fast_stop_candidate"] is True
    # without the pure-speech hint the same audio is held (legacy behaviour)
    b = asm()
    assert b.add(seg(2.8), 1, False, now=0.0) == []
    assert b.pending == 1


def test_speech_duration_drives_min_segment_but_cap_uses_audio():
    a = asm(min_segment_s=0.5, fast_stop_max_s=0)
    assert a.add(seg(2.0), 1, False, now=0.0, speech_duration_s=0.2) == []
    assert a.pending == 0
    b = asm(max_turn_s=4, fast_stop_max_s=0)
    b.add(seg(3), 1, False, now=0.0, speech_duration_s=0.6)
    out = b.add(seg(3), 1, False, now=0.1, speech_duration_s=0.6)
    assert len(out) == 1                     # 6 s of real audio hit the cap


def test_privacy_epoch_stored_per_turn():
    a = asm(fast_stop_max_s=0)
    a.add(seg(3), 1, False, now=0.0, privacy_epoch="e1")
    a.add(seg(3), 1, False, now=0.5, privacy_epoch="e2")
    turn = a.poll(now=9.0)
    assert turn["privacy_epoch"] == "e1"     # epoch of the turn's first segment
    assert asm().add(seg(3), 1, True, now=0.0, privacy_epoch="x")[0]["privacy_epoch"] == "x"


def _make_listener(monkeypatch, cfg_turn):
    monkeypatch.setitem(sys.modules, "sounddevice", types.ModuleType("sounddevice"))
    sys.modules.pop("core.continuous_listener", None)
    from core import privacy_gate
    privacy_gate.reset_privacy_gate_singleton_for_tests()
    from core.continuous_listener import ContinuousListener

    class Cfg(dict):
        def get(self, path, default=None):
            d = self
            for p in path.split("."):
                if isinstance(d, dict) and p in d:
                    d = d[p]
                else:
                    return default
            return d

    q = queue.Queue()
    lst = ContinuousListener(Cfg({"vad": {"aggressiveness": 2, "buffer_duration": 1.0},
                                  "turn": cfg_turn}),
                             stt=None, on_command=lambda *_: None, audio_queue=q)
    return lst, q, privacy_gate


def test_privacy_flush_bumps_generation_and_drains_queue(listener):
    lst, q = listener
    q.put({"audio": seg(1), "capture_generation": lst._capture_generation})
    q.put(None)                               # shutdown sentinel must survive
    gen = lst._capture_generation
    lst._privacy_flush_speech_buffer()
    assert lst._capture_generation == gen + 1
    assert q.get_nowait() is None
    assert q.empty()


def test_privacy_epoch_enforced_per_turn(listener):
    lst, q = listener
    gate = lst._privacy_gate
    old = gate.epoch()
    turn = {"audio": seg(1), "capture_generation": lst._capture_generation,
            "during_tts": False, "privacy_epoch": old}
    gate._epoch = "changed"                   # simulate a privacy transition
    assert lst._put_turn(dict(turn), recheck_generation=False) is False
    assert q.empty()
    turn["privacy_epoch"] = gate.epoch()
    assert lst._put_turn(turn) is True and not q.empty()


def test_release_carries_epoch_of_its_own_segments(listener):
    lst, q = listener
    lst._turn_assembler.fast_stop_max_s = 0
    lst._submit_segment(seg(3), lst._capture_generation, False)
    item = q.get(timeout=3)
    assert item["privacy_epoch"] == lst._privacy_gate.epoch()


def test_listener_fast_stop_with_preroll_and_trailing_silence(listener):
    lst, q = listener
    lst._turn_assembler.grace_s = 100
    # 1.0 s pre-roll + 1.0 s speech + 0.8 s trailing silence
    lst._submit_segment(seg(2.8), lst._capture_generation, False, speech_duration_s=1.0)
    item = q.get_nowait()
    assert item["fast_stop_candidate"] is True


def test_process_speech_measures_pure_speech(listener):
    lst, q = listener
    lst.device_sample_rate = SR
    lst._privacy_gate  # allowed by default
    frame = lst.frame_size
    silence_frames = 25
    lst.vad.silence_frames = silence_frames
    lst._pre_speech_audio = seg(1.0)
    lst._collection_generation = lst._capture_generation
    lst._collection_during_tts = False
    nframes = 60
    lst.speech_buffer = [np.full(frame, 0.1, dtype=np.float32) for _ in range(nframes)]
    lst.collecting_speech = True
    lst._turn_assembler.grace_s = 100
    lst._process_speech()
    item = q.get_nowait()
    assert item["fast_stop_candidate"] is True
    # audio keeps pre-roll + trailing silence (real audio for STT)
    assert item["audio"].shape[0] == SR + nframes * frame


def test_second_segment_preroll_trimmed_no_duplicate_audio(listener):
    lst, q = listener
    lst.device_sample_rate = SR
    lst.vad.silence_frames = 0
    lst._turn_assembler.grace_s = 100
    lst._turn_assembler.fast_stop_max_s = 0
    lst._turn_assembler.gap_s = 0.0
    frame = lst.frame_size

    def run(start_ts, end_ts_offset=0.0):
        lst._pre_speech_audio = seg(1.0)
        lst._collection_generation = lst._capture_generation
        lst._collection_during_tts = False
        lst._collection_start_ts = start_ts
        lst.speech_buffer = [np.full(frame, 0.1, dtype=np.float32) for _ in range(SR // frame * 2)]
        lst.collecting_speech = True
        lst._process_speech()

    run(0.0)
    first_len = lst._turn_assembler._segments[0].shape[0]
    assert first_len == SR + (SR // frame * 2) * frame
    # next segment starts 0.3 s after the previous one ended
    lst._last_segment_end_ts = 100.0
    run(100.3)
    second_len = lst._turn_assembler._segments[1].shape[0]
    speech = (SR // frame * 2) * frame
    assert abs(second_len - (speech + int(0.3 * SR))) <= 1
    # no held turn -> full pre-roll kept
    lst._turn_assembler.clear()
    lst._last_segment_end_ts = 100.0
    run(100.3)
    assert lst._turn_assembler._segments[0].shape[0] == SR + speech


def test_stop_joins_turn_thread(listener):
    lst, q = listener
    lst._turn_assembler.grace_s = 100
    lst._submit_segment(seg(3), lst._capture_generation, False)
    lst._turn_assembler.fast_stop_max_s = 0
    lst._submit_segment(seg(3), lst._capture_generation, False)
    t = lst._turn_thread
    assert t is not None and t.is_alive()
    lst.stop()
    assert not t.is_alive()
    assert lst._turn_assembler.pending == 0


def test_disabled_turn_keeps_legacy_shape(monkeypatch):
    lst, q, pg = _make_listener(monkeypatch, {"enabled": False})
    try:
        assert lst._turn_assembler is None
        lst._submit_segment(seg(2), 3, False, speech_duration_s=1.0)
        item = q.get_nowait()
        assert set(item) == {"audio", "capture_generation", "during_tts"}
    finally:
        pg.reset_privacy_gate_singleton_for_tests()
