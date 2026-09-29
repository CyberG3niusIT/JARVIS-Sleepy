"""Desktop context window must never change the voice daemon's SQLite store."""

import hashlib
import sqlite3
import time

from core.context_window import get_context_window


class _Config:
    def __init__(self, db_path):
        self.db_path = db_path

    def get(self, key, default=None):
        values = {
            "context_window.enabled": True,
            "context_window.db_path": str(self.db_path),
            "context_window.segment_retention_days": 7,
        }
        return values.get(key, default)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_read_only_context_loads_old_segments_without_pruning_or_writing(tmp_path):
    db_path = tmp_path / "memory.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE topic_segments (
                segment_id TEXT PRIMARY KEY, session_id TEXT, label TEXT,
                start_time REAL, end_time REAL, messages_json TEXT,
                embedding BLOB, token_count INTEGER, summary TEXT,
                created_at REAL, user_id TEXT
            )
        """)
        conn.execute("""
            INSERT INTO topic_segments VALUES
            ('old', 'owner', 'old topic', ?, ?, '[]', NULL, 0, '', ?, 'primary_user')
        """, (time.time() - 10 * 86400,) * 3)

    before = _digest(db_path)
    context = get_context_window(_Config(db_path), None, read_only=True)
    context.load_prior_segments()
    context._cleanup_old_segments()
    context._update_segment_summary("old", "changed")
    context._persist_segment(context.segments[0])
    context.on_message({"role": "user", "content": "should not be ingested"})
    context.flush()

    assert [segment.segment_id for segment in context.segments] == ["old"]
    assert _digest(db_path) == before
    with sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True) as conn:
        assert conn.execute("SELECT COUNT(*) FROM topic_segments").fetchone()[0] == 1


def test_read_only_context_does_not_create_a_missing_store(tmp_path):
    db_path = tmp_path / "missing" / "memory.db"
    context = get_context_window(_Config(db_path), None, read_only=True)
    context.load_prior_segments(fallback_messages=[{"role": "user", "content": "old"}])
    assert context.segments == []
    assert not db_path.exists()
