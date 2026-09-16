"""Unit tests for core/latency_tracker.py — real per-turn latency
instrumentation (not just documentation). No pipeline/hardware needed:
the tracker is pure timestamp bookkeeping.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

from core.latency_tracker import LatencyTracker


class _NullLogger:
    def __init__(self):
        self.messages = []

    def info(self, msg, *a, **k):
        self.messages.append(msg)

    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


class TestBasicMarking:
    def test_command_received_marked_on_init(self):
        t = LatencyTracker()
        assert t.has("command_received")

    def test_mark_records_monotonic_timestamp(self):
        t = LatencyTracker()
        time.sleep(0.01)
        t.mark("router_done")
        ms = t._span_ms("command_received", "router_done")
        assert ms is not None
        assert ms >= 5  # allow scheduling jitter, just prove it's real elapsed time

    def test_mark_is_idempotent(self):
        t = LatencyTracker()
        t.mark("llm_first_token")
        first = t._marks["llm_first_token"]
        time.sleep(0.01)
        t.mark("llm_first_token")  # second call for the same stage
        assert t._marks["llm_first_token"] == first

    def test_turn_id_is_stable_and_short(self):
        t = LatencyTracker()
        assert t.turn_id
        assert len(t.turn_id) <= 12

    def test_custom_turn_id_used_verbatim(self):
        t = LatencyTracker(turn_id="abc123")
        assert t.turn_id == "abc123"


class TestSummaryLine:
    def test_summary_includes_reached_spans_only(self):
        t = LatencyTracker()
        t.mark("router_done")
        line = t.summary_line()
        assert "Routing+Memory" in line
        assert "LLM TTFT" not in line  # llm_start/llm_first_token never marked

    def test_summary_never_crashes_with_no_marks_beyond_init(self):
        t = LatencyTracker()
        line = t.summary_line()
        assert t.turn_id in line

    def test_full_turn_summary_has_all_spans(self):
        t = LatencyTracker()
        for stage in ["router_done", "llm_start", "llm_first_token",
                      "first_speakable_chunk", "tts_first_pcm", "response_done"]:
            time.sleep(0.001)
            t.mark(stage)
        line = t.summary_line()
        for label in ["Routing+Memory", "LLM TTFT", "Erster sprechbarer Chunk",
                      "TTS erstes PCM", "Gesamt"]:
            assert label in line, f"missing '{label}' in: {line}"


class TestMetadata:
    def test_as_metadata_has_turn_id_and_offsets(self):
        t = LatencyTracker()
        t.mark("router_done")
        meta = t.as_metadata()
        assert meta["turn_id"] == t.turn_id
        assert "command_received" in meta["offsets_ms"]
        assert meta["offsets_ms"]["command_received"] == 0.0

    def test_offsets_are_relative_to_command_received(self):
        t = LatencyTracker()
        time.sleep(0.01)
        t.mark("router_done")
        meta = t.as_metadata()
        assert meta["offsets_ms"]["router_done"] >= 5


class TestEmit:
    def test_emit_logs_summary_and_does_not_raise_without_event_logger(self):
        t = LatencyTracker()
        t.mark("router_done")
        logger = _NullLogger()
        t.emit(logger, config=None)  # event_logger likely unconfigured in tests
        assert any("JARVIS LATENCY" in m for m in logger.messages)

    def test_emit_never_raises_even_if_event_logger_broken(self, monkeypatch):
        import core.latency_tracker as lt_module

        def boom(*a, **k):
            raise RuntimeError("event logger exploded")

        # Patch the module-level import target used inside emit()'s
        # deferred `from core.event_logger import get_event_logger`.
        import core.event_logger as event_logger_module
        monkeypatch.setattr(event_logger_module, "get_event_logger", boom)

        t = LatencyTracker()
        logger = _NullLogger()
        t.emit(logger, config=None)  # must not raise
        assert logger.messages  # summary line still logged
