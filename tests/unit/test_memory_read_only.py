"""Read-only MemoryManager (jarvis_web.py --desktop-mode): reads work, every write is refused and logged.

Real temp-file SQLite and a real FAISS index, no mocks of the stores: the point is that the owner's
files stay byte-identical while a second, read-only manager is alive.
"""

import hashlib
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import numpy as np
import pytest

from core.memory_manager import MemoryManager


class _FakeConfig(dict):
    def get(self, path, default=None):
        node = self
        for part in path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node


class _Embedder:
    def __init__(self, dim=4):
        self.dim = dim

    def get_sentence_embedding_dimension(self):
        return self.dim

    def _vector(self, text):
        vector = np.zeros(self.dim, dtype=np.float32)
        vector[len(text) % self.dim] = 1.0
        return vector

    def encode(self, text, normalize_embeddings=True, show_progress_bar=False, batch_size=None):
        if isinstance(text, list):
            return np.array([self._vector(item) for item in text], dtype=np.float32)
        return self._vector(text)


def _config(tmp_path):
    return _FakeConfig({"conversational_memory": {
        "db_path": str(tmp_path / "data" / "memory.db"),
        "faiss_index_path": str(tmp_path / "data" / "faiss"),
    }})


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fact(content="the user's favorite editor is VS Code", subject="editor"):
    return {"user_id": "primary_user", "category": "preference", "subject": subject, "content": content,
            "value": None, "source": "explicit", "confidence": 0.9, "source_messages": "[]"}


@pytest.fixture
def owner(tmp_path):
    """The voice daemon's manager: writes a fact, an interaction and a persisted FAISS index."""
    manager = MemoryManager(_config(tmp_path), conversation=None, embedding_model=_Embedder())
    manager.store_fact(_fact())
    manager.persist_interaction("research", "query", "answer")
    manager.index_message({"content": "a message that is long enough", "timestamp": 1.0, "role": "user"})
    manager.save()
    return manager


def _stores(tmp_path):
    return {
        "db": tmp_path / "data" / "memory.db",
        "index": tmp_path / "data" / "faiss" / "default.index",
        "meta": tmp_path / "data" / "faiss" / "default_meta.jsonl",
    }


def _read_only(tmp_path, embedder=None):
    manager = MemoryManager(_config(tmp_path), conversation=None, embedding_model=embedder or _Embedder(),
                            read_only=True)
    manager.logger = MagicMock()
    return manager


def test_default_manager_is_writable_and_unchanged(owner):
    assert owner.read_only is False and owner.rejected_writes == {}
    assert owner.get_fact_count()  # the owner really wrote its fact


def test_read_only_reads_the_owners_facts_interactions_and_index(owner, tmp_path):
    reader = _read_only(tmp_path)
    assert reader.read_only is True
    assert [fact["content"] for fact in reader.get_facts()] == ["the user's favorite editor is VS Code"]
    assert len(reader.get_recent_interactions(limit=5)) == 1
    assert reader.faiss_index.ntotal == 1
    assert reader.search_history("a message that is long enough", top_k=1)


def test_read_only_never_changes_the_owners_files(owner, tmp_path):
    before = {name: _digest(path) for name, path in _stores(tmp_path).items()}
    reader = _read_only(tmp_path)
    reader.get_facts()
    reader.search_history("anything long enough", top_k=1)
    reader.save()
    assert {name: _digest(path) for name, path in _stores(tmp_path).items()} == before


def test_every_write_path_is_rejected_logged_and_counted(owner, tmp_path):
    before = {name: _digest(path) for name, path in _stores(tmp_path).items()}
    reader = _read_only(tmp_path)
    fact_id = reader.get_facts()[0]["fact_id"]

    assert reader.store_fact(_fact("another fact", subject="other")) is None
    assert reader.update_fact(fact_id, confidence=0.1) is False
    assert reader.delete_fact(fact_id) is False
    assert reader.delete_fact(fact_id, soft=False) is False
    assert reader.persist_interaction("research", "q", "a") is None
    assert reader.promote_session_artifacts([object()], "window") is None
    assert reader.cleanup_old_interactions(retention_days=0) is None
    assert reader.run_decay_pass() == {"archived_count": 0, "archived_fact_ids": []}
    assert reader.run_consolidation() == {"skipped": True, "reason": "read_only"}
    assert reader._merge_duplicate_excluded_candidates() == {"merged_count": 0}
    assert reader.backfill_history() == 0
    assert reader.extract_facts_realtime({"role": "user", "content": "my name is Test User"}) == []
    reader.index_message({"content": "a message that is long enough", "timestamp": 2.0, "role": "user"})
    reader.on_message({"role": "user", "content": "a message that is long enough"})
    assert reader.handle_forget("forget my editor") == MemoryManager.READ_ONLY_MESSAGE
    assert reader.confirm_forget() == MemoryManager.READ_ONLY_MESSAGE
    reader._save_faiss_index()

    assert set(reader.rejected_writes) >= {
        "store_fact", "update_fact", "delete_fact", "persist_interaction", "promote_session_artifacts",
        "cleanup_old_interactions", "run_decay_pass", "run_consolidation",
        "merge_duplicate_excluded_candidates", "backfill_history", "extract_facts_realtime", "index_message",
        "on_message", "handle_forget", "confirm_forget", "faiss_save",
    }
    assert reader.rejected_writes["delete_fact"] == 2
    assert reader.logger.warning.call_count == sum(reader.rejected_writes.values())
    assert all("read-only" in call.args[0] for call in reader.logger.warning.call_args_list)
    assert reader.faiss_index.ntotal == 1  # nothing slipped into the in-memory index either
    assert {name: _digest(path) for name, path in _stores(tmp_path).items()} == before


def test_a_stale_read_only_process_cannot_overwrite_newer_owner_vectors(owner, tmp_path):
    reader = _read_only(tmp_path)  # loaded with 1 vector
    owner.index_message({"content": "a second message that is long enough", "timestamp": 3.0, "role": "user"})
    owner.save()  # the owner now has 2 vectors on disk
    newer = _digest(_stores(tmp_path)["index"])

    reader.index_message({"content": "third message from the reader", "timestamp": 4.0, "role": "user"})
    reader.save()
    reader._faiss_dirty = 99  # even a dirty counter must not let it write
    reader.save()

    assert _digest(_stores(tmp_path)["index"]) == newer
    assert MemoryManager(_config(tmp_path), None, _Embedder()).faiss_index.ntotal == 2


def test_read_only_init_does_not_create_or_migrate_or_clean_anything(tmp_path):
    # No stores at all: nothing may be created (no directory, no db, no index).
    reader = _read_only(tmp_path)
    assert not (tmp_path / "data").exists()
    assert reader.faiss_index is not None and reader.faiss_index.ntotal == 0


def test_read_only_leaves_the_owners_temp_files_alone(owner, tmp_path):
    tmp_index = tmp_path / "data" / "faiss" / "default.index.tmp"
    tmp_index.write_bytes(b"owner is writing right now")
    _read_only(tmp_path)
    assert tmp_index.read_bytes() == b"owner is writing right now"
    MemoryManager(_config(tmp_path), None, _Embedder())  # a normal manager still cleans it up
    assert not tmp_index.exists()


def test_read_only_never_rebuilds_an_index_with_another_dimension(owner, tmp_path):
    before = {name: _digest(path) for name, path in _stores(tmp_path).items()}
    reader = _read_only(tmp_path, embedder=_Embedder(dim=8))
    assert reader.faiss_index is None and reader.faiss_metadata == []
    reader.save()
    assert {name: _digest(path) for name, path in _stores(tmp_path).items()} == before


def test_read_only_repairs_a_desync_in_memory_only(owner, tmp_path):
    meta = _stores(tmp_path)["meta"]
    meta.write_text("", encoding="utf-8")  # 1 vector, 0 metadata entries
    before = _digest(meta)
    reader = _read_only(tmp_path)
    assert reader.faiss_index.ntotal == 0 and reader.faiss_metadata == []
    assert _digest(meta) == before


def test_factory_passes_read_only_through(tmp_path, monkeypatch):
    import core.memory_manager as module
    monkeypatch.setattr(module, "_instance", None)
    manager = module.get_memory_manager(_config(tmp_path), None, _Embedder(), read_only=True)
    assert manager.read_only is True
    assert module.get_memory_manager() is manager
