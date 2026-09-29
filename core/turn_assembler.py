"""
Turn Assembler

Pure logic (no audio hardware, no sounddevice import) that aggregates several
adjacent VAD speech segments -- separated by natural pauses -- into ONE user
turn before it is handed to the STT queue.

Policy summary
--------------
* Normal segments are HELD. The merged turn is released by ``poll()`` once
  ``grace_s`` has elapsed since the END of the last segment.
* Hard caps bound aggregation (noise / endless talk cannot grow the buffer
  unboundedly): ``max_turn_s`` (audio duration AND wall-clock since first
  held segment) and ``max_segments`` force an immediate release.
* ``during_tts`` segments are NEVER merged. They are returned immediately as
  their own turn (existing barge-in path stays untouched).
* Stop fast path: a short segment (<= ``fast_stop_max_s``) outside TTS that
  OPENS a turn (nothing held) is flagged ``fast_stop_candidate=True`` and returned immediately WITHOUT
  waiting for grace. Choice for already-held earlier segments: they are
  (only possible when nothing is held: a short segment arriving while a turn
  is held is a continuation and is merged, never fast-pathed).
  ``add(speech_duration_s=...)`` lets the caller pass the pure speech length
  (without pre-roll / trailing silence); it drives the fast-stop and
  min_segment decisions, while max_turn accounting uses the real audio.
  Downstream STT decides whether the short segment is a stop-only command;
  on a match the caller invokes ``discard()`` to drop anything still held.
* A generation mismatch on ``add()`` drops the held buffer first (stale audio
  from an interrupted turn must never be merged with fresh audio).
* ``clear()`` / ``flush()`` / ``discard()`` drop the buffer (privacy, pause).

All public methods are thread-safe.
"""

import itertools
import threading
import time
from typing import Callable, List, Optional

import numpy as np


class TurnAssembler:
    def __init__(self, grace_s: float = 1.2, max_turn_s: float = 20.0,
                 max_segments: int = 8, sample_rate: int = 16000,
                 clock: Callable[[], float] = time.monotonic,
                 gap_s: float = 0.0, fast_stop_max_s: float = 1.6,
                 min_segment_s: float = 0.0):
        self.grace_s = float(grace_s)
        self.max_turn_s = float(max_turn_s)
        self.max_segments = max(1, int(max_segments))
        self.sample_rate = int(sample_rate)
        self.gap_s = max(0.0, float(gap_s))
        self.fast_stop_max_s = float(fast_stop_max_s)
        self.min_segment_s = max(0.0, float(min_segment_s))
        self._clock = clock
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._segments: List[np.ndarray] = []
        self._generation: Optional[int] = None
        self._epoch = None
        self._first_ts = 0.0
        self._last_end_ts = 0.0

    # ------------------------------------------------------------------ state
    @property
    def pending(self) -> int:
        """Number of segments currently held."""
        with self._lock:
            return len(self._segments)

    def _held_seconds(self) -> float:
        return sum(len(s) for s in self._segments) / float(self.sample_rate)

    def _make_turn(self, segments, generation, during_tts, fast=False,
                   privacy_epoch=None) -> dict:
        if len(segments) == 1:
            audio = segments[0]
        else:
            parts = []
            gap = (np.zeros(int(self.gap_s * self.sample_rate), dtype=np.float32)
                   if self.gap_s > 0 else None)
            for i, seg in enumerate(segments):
                if i and gap is not None:
                    parts.append(gap)
                parts.append(seg)
            audio = np.concatenate(parts)
        return {
            "audio": audio,
            "capture_generation": generation,
            "during_tts": during_tts,
            "segments": len(segments),
            "turn_id": next(self._ids),
            "fast_stop_candidate": fast,
            "privacy_epoch": privacy_epoch,
        }

    def _release_locked(self) -> Optional[dict]:
        if not self._segments:
            return None
        turn = self._make_turn(self._segments, self._generation, False,
                               privacy_epoch=self._epoch)
        self._segments = []
        self._generation = None
        self._epoch = None
        return turn

    # -------------------------------------------------------------------- API
    def add(self, segment_audio, generation: int, during_tts: bool = False,
            now: Optional[float] = None, speech_duration_s: Optional[float] = None,
            privacy_epoch=None) -> List[dict]:
        """Add a finished speech segment (``now`` = time the segment ended).

        ``speech_duration_s``: pure speech length (no pre-roll / trailing
        silence); falls back to the audio length. ``privacy_epoch`` is stored
        with the held turn (opened by its first segment) and returned in the
        released turn dict.

        Returns a list of turns that must be forwarded NOW (usually empty).
        """
        now = self._clock() if now is None else now
        seg = np.asarray(segment_audio, dtype=np.float32)
        audio_dur = len(seg) / float(self.sample_rate)
        dur = audio_dur if speech_duration_s is None else max(0.0, float(speech_duration_s))
        out: List[dict] = []
        with self._lock:
            # Stale generation: drop what we hold before anything else.
            if self._segments and self._generation != generation:
                self._segments = []
                self._generation = None
                self._epoch = None

            if during_tts:
                # Never merged, never held: barge-in path stays immediate.
                out.append(self._make_turn([seg], generation, True,
                                           privacy_epoch=privacy_epoch))
                return out

            if dur < self.min_segment_s:
                return out  # too short to be speech worth aggregating

            # Fast path only for a short segment that OPENS a turn. A short
            # segment arriving while a turn is held is a continuation
            # ("... Wie alt sind Anna und Ben heute?") and is merged.
            if (0 < self.fast_stop_max_s and dur <= self.fast_stop_max_s
                    and not self._segments):
                out.append(self._make_turn([seg], generation, False, fast=True,
                                           privacy_epoch=privacy_epoch))
                return out

            if not self._segments:
                self._generation = generation
                self._epoch = privacy_epoch
                self._first_ts = now
            self._segments.append(seg)
            self._last_end_ts = now

            if (len(self._segments) >= self.max_segments
                    or self._held_seconds() >= self.max_turn_s):
                released = self._release_locked()
                if released is not None:
                    out.append(released)
        return out

    def poll(self, now: Optional[float] = None) -> Optional[dict]:
        """Return the merged turn if grace elapsed (or a hard cap hit)."""
        now = self._clock() if now is None else now
        with self._lock:
            if not self._segments:
                return None
            if (now - self._last_end_ts >= self.grace_s
                    or now - self._first_ts >= self.max_turn_s):
                return self._release_locked()
            return None

    def clear(self) -> None:
        """Drop everything held (privacy flush, pause, invalidate)."""
        with self._lock:
            self._segments = []
            self._generation = None
            self._epoch = None

    flush = clear    # drop semantics (privacy): flush never forwards audio
    discard = clear  # called by the stop matcher: drop held buffer, no turn
