"""Unit tests for session #6 P0 item 3: conversation persistence must be
gated by PrivacyGate before disk (chat_history.jsonl), context-window
(topic-segment SQLite + LLM summarization), memory, and content-logs —
not just memory (already covered by session #5).

Real objects throughout (tmp_path-backed ConversationManager/
ContextWindow), no mocking of the persistence layer itself — both
modules have no sounddevice/torch import blocker, unlike
continuous_listener.py.
"""

import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.conversation import ConversationManager
from core.context_window import ContextWindow
from core.privacy_gate import (
    Capability,
    PrivacyMode,
    get_privacy_gate,
    reset_privacy_gate_singleton_for_tests,
)


class _FakeConfig(dict):
    def get(self, path, default=None):
        parts = path.split(".")
        d = self
        for p in parts:
            if isinstance(d, dict) and p in d:
                d = d[p]
            else:
                return default
        return d


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_privacy_gate_singleton_for_tests()
    yield
    reset_privacy_gate_singleton_for_tests()


@pytest.fixture
def conv_cfg(tmp_path):
    return _FakeConfig({"system": {"storage_path": str(tmp_path)}})


@pytest.fixture
def conv(conv_cfg):
    return ConversationManager(conv_cfg)


class TestChatHistoryJsonlDeniedDuringPrivacy:
    def test_message_not_written_to_jsonl_during_privacy(self, conv, conv_cfg):
        gate = get_privacy_gate(conv_cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        conv.add_message("user", "geheime Nachricht während Privacy")

        assert not conv.chat_history_file.exists() or conv.chat_history_file.read_text() == ""

    def test_message_written_normally_outside_privacy(self, conv):
        conv.add_message("user", "normale Nachricht")

        assert conv.chat_history_file.exists()
        lines = conv.chat_history_file.read_text().strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["content"] == "normale Nachricht"

    def test_privacy_message_not_retroactively_written_after_exit(self, conv, conv_cfg):
        gate = get_privacy_gate(conv_cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        conv.add_message("user", "geheime Nachricht")
        gate.exit(actor="test")

        conv.add_message("user", "Nachricht nach Exit")

        assert conv.chat_history_file.exists()
        lines = conv.chat_history_file.read_text().strip().split("\n")
        contents = [json.loads(l)["content"] for l in lines]
        assert "geheime Nachricht" not in contents
        assert "Nachricht nach Exit" in contents

    def test_session_history_ram_still_updated_during_privacy(self, conv, conv_cfg):
        """Deliberate design choice, documented here: privacy blocks
        durable persistence (jsonl/memory/context-summary/content-logs)
        but not the in-process session_history list itself — the
        console/web typed-text path doesn't go through MIC_INGEST/STT at
        all, so the live turn-by-turn exchange must still work for the
        user to e.g. type "privacy beenden" and get a coherent reply.
        Nothing here is written to disk (verified by the jsonl test
        above) and it vanishes on process restart."""
        gate = get_privacy_gate(conv_cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        conv.add_message("user", "während privacy gesagt")

        assert any(m["content"] == "während privacy gesagt" for m in conv.session_history)


class TestDebugLoggerContentDuringPrivacy:
    """Session #7 finding: add_message()'s own debug log —
    self.logger.debug(f"Added {role} message: {content[:50]}...") — went
    through core/logger.py's standard logging output unconditionally.
    core/logger.py has no PrivacyGate awareness (and shouldn't — content
    safety is each caller's responsibility, same as debug_logger.py's
    own gate), so this was a real content leak into log files during
    privacy, separate from the already-gated chat_history.jsonl write."""

    def test_debug_log_omits_content_during_privacy(self, conv, conv_cfg):
        gate = get_privacy_gate(conv_cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        calls = []
        conv.logger.debug = lambda msg, *a, **k: calls.append(msg)

        conv.add_message("user", "geheimer Inhalt der nirgendwo auftauchen darf")

        assert calls  # still logs something (metadata)
        assert all("geheimer Inhalt" not in c for c in calls)

    def test_debug_log_includes_content_outside_privacy(self, conv):
        calls = []
        conv.logger.debug = lambda msg, *a, **k: calls.append(msg)

        conv.add_message("user", "normaler Inhalt sichtbar im Log")

        assert any("normaler Inhalt" in c for c in calls)

    def test_debug_log_metadata_only_has_no_content_after_exit_either(self, conv, conv_cfg):
        gate = get_privacy_gate(conv_cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        calls = []
        conv.logger.debug = lambda msg, *a, **k: calls.append(msg)

        conv.add_message("user", "während privacy")
        gate.exit(actor="test")
        conv.add_message("user", "nach exit sichtbar")

        privacy_call = calls[0]
        post_exit_call = calls[1]
        assert "während privacy" not in privacy_call
        assert "nach exit sichtbar" in post_exit_call


@pytest.fixture
def ctx_cfg(tmp_path):
    return _FakeConfig({
        "context_window": {
            "enabled": True,
            "db_path": str(tmp_path / "context.db"),
            "summarize_closed_segments": True,
            "topic_shift_threshold": 0.01,  # force a topic shift easily
        },
    })


class _FakeEmbeddingModel:
    """Deterministic fake — orthogonal vectors force a topic shift on
    every second call, so _close_segment()/_persist_segment() actually
    fire without needing a real embedding model."""

    def __init__(self):
        self._toggle = False

    def encode(self, text, normalize_embeddings=True, show_progress_bar=False):
        import numpy as np
        self._toggle = not self._toggle
        vec = np.zeros(4, dtype=np.float32)
        vec[0 if self._toggle else 1] = 1.0
        return vec


@pytest.fixture
def ctx(ctx_cfg):
    return ContextWindow(ctx_cfg, embedding_model=_FakeEmbeddingModel())


def _segment_count_in_db(ctx):
    import sqlite3
    conn = sqlite3.connect(str(ctx._db_path))
    try:
        return conn.execute("SELECT COUNT(*) FROM topic_segments").fetchone()[0]
    finally:
        conn.close()


class TestContextWindowDeniedDuringPrivacy:
    def test_on_message_skips_ingestion_during_privacy(self, ctx, ctx_cfg):
        gate = get_privacy_gate(ctx_cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        ctx.on_message({"role": "user", "content": "geheim", "timestamp": time.time()})

        assert ctx._current_segment is None  # nothing ingested at all

    def test_on_message_works_normally_outside_privacy(self, ctx):
        ctx.on_message({"role": "user", "content": "normal", "timestamp": time.time()})
        assert ctx._current_segment is not None

    def test_persist_segment_denied_during_privacy_writes_nothing(self, ctx, ctx_cfg):
        gate = get_privacy_gate(ctx_cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        # Directly exercise the write path a background thread would hit
        # (on_message() being gated already prevents reaching this in
        # practice — this is the second line of defense, same pattern
        # as memory_manager.store_fact()).
        from core.context_window import TopicSegment
        seg = TopicSegment(
            segment_id="seg1", messages=[{"role": "user", "content": "geheim"}],
            embedding=None, start_time=time.time(), end_time=time.time(),
            token_count=5, label="test",
        )
        ctx._persist_segment(seg)

        assert _segment_count_in_db(ctx) == 0

    def test_persist_segment_works_normally_outside_privacy(self, ctx):
        from core.context_window import TopicSegment
        seg = TopicSegment(
            segment_id="seg2", messages=[{"role": "user", "content": "normal"}],
            embedding=None, start_time=time.time(), end_time=time.time(),
            token_count=5, label="test",
        )
        ctx._persist_segment(seg)

        assert _segment_count_in_db(ctx) == 1

    def test_persist_segment_rejects_stale_epoch(self, ctx, ctx_cfg):
        """Simulates _close_segment()'s background-thread race: epoch
        captured while NORMAL, privacy enter+exit completes before the
        thread's write runs — mode() reads NORMAL again, but the write
        must still be rejected."""
        gate = get_privacy_gate(ctx_cfg)
        captured_epoch = gate.epoch()
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        gate.exit(actor="test")
        assert gate.mode() == PrivacyMode.NORMAL

        from core.context_window import TopicSegment
        seg = TopicSegment(
            segment_id="seg3", messages=[{"role": "user", "content": "raced"}],
            embedding=None, start_time=time.time(), end_time=time.time(),
            token_count=5, label="test",
        )
        ctx._persist_segment(seg, captured_epoch=captured_epoch)

        assert _segment_count_in_db(ctx) == 0

    def test_summarize_segment_denied_during_privacy_makes_no_llm_call(self, ctx, ctx_cfg, monkeypatch):
        gate = get_privacy_gate(ctx_cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        called = []
        monkeypatch.setattr(
            "core.context_window.requests.post",
            lambda *a, **k: called.append(True),
        )

        from core.context_window import TopicSegment
        seg = TopicSegment(
            segment_id="seg4", messages=[{"role": "user", "content": "geheim"}, {"role": "assistant", "content": "ok"}],
            embedding=None, start_time=time.time(), end_time=time.time(),
            token_count=5, label="test",
        )
        ctx._summarize_segment(seg)

        assert called == []

    def test_close_segment_end_to_end_denied_during_privacy(self, ctx, ctx_cfg):
        """Full path: two on_message() calls that would normally trigger
        a topic shift -> _close_segment() -> persist+summarize threads.
        With privacy active throughout, nothing should be ingested or
        persisted."""
        gate = get_privacy_gate(ctx_cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        ctx.on_message({"role": "user", "content": "erste geheime Nachricht", "timestamp": time.time()})
        ctx.on_message({"role": "user", "content": "zweite geheime Nachricht", "timestamp": time.time()})

        assert ctx._current_segment is None
        assert _segment_count_in_db(ctx) == 0
