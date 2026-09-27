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


class TestBackfillWithExplicitTimestamp:
    """Session #7: mark(stage, at=...) lets a caller backfill a stage
    that happened on a different thread before this tracker even
    existed (e.g. speech_end on continuous_listener.py's callback
    thread, captured before _handle_command() creates the tracker) —
    see the _STAGE_ORDER comment in core/latency_tracker.py for the
    full reasoning and current wiring status."""

    def test_mark_with_at_uses_explicit_timestamp(self):
        t = LatencyTracker()
        past = time.monotonic() - 0.5  # 500ms "in the past"
        t.mark("speech_end", at=past)
        assert t._marks["speech_end"] == past

    def test_backfilled_stage_produces_correct_span(self):
        past = time.monotonic() - 0.2  # speech ended 200ms before the tracker existed
        t = LatencyTracker()
        t.mark("speech_end", at=past)
        ms = t._span_ms("speech_end", "command_received")
        assert ms is not None
        assert 150 <= ms <= 400  # allow scheduling jitter around the 200ms target

    def test_backfilled_stage_appears_in_summary_line(self):
        past = time.monotonic() - 0.05
        t = LatencyTracker()
        t.mark("speech_end", at=past)
        line = t.summary_line()
        assert "Speech-End -> Command" in line

    def test_no_backfill_leaves_existing_behavior_unchanged(self):
        """A tracker that never receives speech_end/stt_start/stt_end
        must behave exactly as before this change — those spans simply
        don't appear, nothing errors."""
        t = LatencyTracker()
        t.mark("router_done")
        line = t.summary_line()
        assert "Speech-End -> Command" not in line
        assert "STT" not in line  # "STT" span label, not incidental substring match elsewhere
        assert "Routing+Memory" in line

    def test_mark_without_at_still_uses_now(self):
        """Default behavior (no `at`) is unaffected by the new parameter."""
        t = LatencyTracker()
        before = time.monotonic()
        t.mark("router_done")
        after = time.monotonic()
        assert before <= t._marks["router_done"] <= after

    def test_backfill_is_idempotent_too(self):
        t = LatencyTracker()
        first_past = time.monotonic() - 1.0
        second_past = time.monotonic() - 0.1
        t.mark("speech_end", at=first_past)
        t.mark("speech_end", at=second_past)  # must not overwrite
        assert t._marks["speech_end"] == first_past

    def test_full_chain_including_new_stages(self):
        speech_end = time.monotonic() - 0.3
        stt_start = speech_end + 0.01
        stt_end = stt_start + 0.15
        t = LatencyTracker()
        t.mark("speech_end", at=speech_end)
        t.mark("stt_start", at=stt_start)
        t.mark("stt_end", at=stt_end)
        for stage in ["router_done", "llm_start", "llm_first_token",
                      "first_speakable_chunk", "tts_first_pcm", "response_done"]:
            t.mark(stage)
        line = t.summary_line()
        for label in ["STT", "Speech-End -> Command", "Routing+Memory",
                      "LLM TTFT", "Gesamt (ab Speech-End)"]:
            assert label in line, f"missing '{label}' in: {line}"


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
