"""Per-turn latency instrumentation for the voice pipeline.

Real monotonic checkpoints, not just documentation — the goal is a
compact, human-readable "JARVIS LATENCY" summary line per turn (never
transcripts/verbose data in the normal log) plus a structured
event_logger emission for anyone building p50/p95 rollups later.

Scope (see docs/ARCHITECTURE.md for the full discussion): this instruments
the portion of the turn that's within core/pipeline.py's control — from
"command handed to the router" through "response fully spoken." It does
NOT cover VAD/STT (those run in core/continuous_listener.py /
core/stt_qwen3.py, on a different thread with no turn-id handed in yet) —
flagged as a known gap, not silently assumed covered.
"""

import threading
import time
import uuid
from typing import Optional


# Ordered so the summary line and the "vorher/stage" delta both read
# naturally top to bottom, matching the flow of a turn.
_STAGE_ORDER = [
    "command_received",
    "router_done",
    "llm_start",
    "llm_first_token",
    "first_speakable_chunk",
    "tts_first_pcm",
    "response_done",
]

# Human-readable label + the (from_stage, to_stage) span it summarizes.
# "Routing" currently includes memory retrieval — ConversationRouter.route()
# does both synchronously and isn't separately instrumented yet (would
# need a checkpoint inside conversation_router.py itself; not done this
# session — see docs/ARCHITECTURE.md).
_SUMMARY_SPANS = [
    ("Routing+Memory", "command_received", "router_done"),
    ("LLM TTFT", "llm_start", "llm_first_token"),
    ("Erster sprechbarer Chunk", "llm_start", "first_speakable_chunk"),
    ("TTS erstes PCM", "first_speakable_chunk", "tts_first_pcm"),
    ("Gesamt", "command_received", "response_done"),
]


class LatencyTracker:
    """One instance per voice-command turn.

    A turn is handled by one coordinator dispatch at a time, but
    mark("tts_first_pcm") is called from StreamingAudioPipeline's own
    background thread via a callback (see core/pipeline.py), while the
    coordinator's thread keeps calling mark() for the other stages —
    so this genuinely is written from two threads concurrently. A lock
    around the dict mutation keeps that safe regardless of dict
    implementation details, rather than relying on CPython's GIL
    happening to make a single dict-item-assignment atomic.
    """

    def __init__(self, turn_id: Optional[str] = None):
        self.turn_id = turn_id or uuid.uuid4().hex[:8]
        self._marks: dict[str, float] = {}
        self._lock = threading.Lock()
        self.mark("command_received")

    def mark(self, stage: str) -> float:
        """Record a monotonic timestamp for `stage`, if not already set.
        Returns the timestamp. Idempotent — a stage already marked keeps
        its first timestamp (e.g. multiple chunks each try to mark
        "first_speakable_chunk"; only the first sticks)."""
        with self._lock:
            if stage not in self._marks:
                self._marks[stage] = time.monotonic()
            return self._marks[stage]

    def has(self, stage: str) -> bool:
        return stage in self._marks

    def _span_ms(self, from_stage: str, to_stage: str) -> Optional[float]:
        if from_stage not in self._marks or to_stage not in self._marks:
            return None
        delta = (self._marks[to_stage] - self._marks[from_stage]) * 1000
        return delta if delta >= 0 else None

    def summary_line(self) -> str:
        """One compact, human-readable line — safe to log at INFO on
        every turn (no transcript content, no per-token spam)."""
        parts = []
        for label, from_stage, to_stage in _SUMMARY_SPANS:
            ms = self._span_ms(from_stage, to_stage)
            if ms is not None:
                parts.append(f"{label}: {ms:.0f}ms")
        if not parts:
            return f"[{self.turn_id}] JARVIS LATENCY: keine Messpunkte erreicht"
        return f"[{self.turn_id}] JARVIS LATENCY — " + " | ".join(parts)

    def as_metadata(self) -> dict:
        """Structured data for event_logger — raw per-stage monotonic
        offsets from command_received, in ms, plus the named spans."""
        with self._lock:
            marks_snapshot = dict(self._marks)
        base = marks_snapshot.get("command_received")
        offsets = {
            stage: round((ts - base) * 1000, 1)
            for stage, ts in marks_snapshot.items()
        } if base is not None else {}
        spans = {
            label: round(ms, 1)
            for label, from_stage, to_stage in _SUMMARY_SPANS
            if (ms := self._span_ms(from_stage, to_stage)) is not None
        }
        return {"turn_id": self.turn_id, "offsets_ms": offsets, "spans_ms": spans}

    def emit(self, logger, config=None):
        """Log the compact summary line and (if event_logger is
        available) a structured event for later rollups."""
        logger.info(self.summary_line())
        try:
            from core.event_logger import get_event_logger
            el = get_event_logger(config)
            if el:
                el.emit(
                    category="performance",
                    event="turn_latency",
                    message=self.summary_line(),
                    severity="info",
                    source="pipeline",
                    stage="turn",
                    status="success",
                    metadata=self.as_metadata(),
                )
        except Exception:
            pass  # instrumentation must never break the voice turn
