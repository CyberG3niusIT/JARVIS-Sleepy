"""Controlled search data through real temporary SQLite writers; no network."""
import sqlite3
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock

import pytest

from core.event_logger import EventLogger
from core.interaction_cache import Artifact, InteractionCache
from core.privacy_gate import Capability


@pytest.fixture
def writers(tmp_path):
    config = {"events.db_path": str(tmp_path / "events.db"),
              "system.storage_path": str(tmp_path)}
    return EventLogger(config), InteractionCache(config)


def artifact():
    return Artifact("controlled-search", 1, 0, "search_result_set",
                    "Controlled snippet and page", "Controlled query", "web_search",
                    provenance={"query": "controlled query", "url": "https://example.invalid"},
                    window_id="test-window")


@pytest.mark.parametrize("content,memory", [(True, True), (False, True),
                                           (True, False), (False, False)])
def test_independent_writer_contract(monkeypatch, writers, content, memory):
    import core.privacy_gate as privacy
    gate = SimpleNamespace(allow=lambda cap: content if cap == Capability.CONTENT_LOGGING else memory)
    monkeypatch.setattr(privacy, "get_privacy_gate", lambda *a: gate)
    events, cache = writers
    notify = Mock()
    events.set_on_emit(notify)
    event_id = events.emit(category="tool_execution", event="tool_completed",
                           message="controlled query", metadata={"query": "controlled query"})
    stored_id = cache.store(artifact())
    assert events.count() == int(content)
    assert notify.call_count == int(content)
    assert bool(event_id) is content
    assert bool(stored_id) is memory
    assert len(cache.get_hot_artifacts("test-window")) == int(memory)
    with sqlite3.connect(str(cache.db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == int(memory)


@pytest.mark.parametrize("failure", ["missing", "exception", "ambiguous"])
def test_gate_failure_skips_writes(monkeypatch, writers, failure):
    import core.privacy_gate as privacy
    if failure == "missing":
        gate = None
    elif failure == "exception":
        gate = SimpleNamespace(allow=Mock(side_effect=RuntimeError("controlled gate failure")))
    else:
        gate = SimpleNamespace(allow=lambda cap: "ALLOW")
    monkeypatch.setattr(privacy, "get_privacy_gate", lambda *a: gate)
    events, cache = writers
    assert events.emit(category="tool_execution", event="tool_completed", message="controlled") is None
    assert cache.store(artifact()) is None
    assert events.count() == 0
    assert cache.get_hot_artifacts("test-window") == []


@pytest.mark.parametrize("value", [False, None, "ALLOW", RuntimeError("gate failed")])
def test_memory_writer_fail_closed(tmp_path, value):
    from core.memory_manager import MemoryManager
    manager = MemoryManager.__new__(MemoryManager)
    manager.read_only = False
    manager._privacy_gate = SimpleNamespace(allow=Mock(side_effect=value)) if isinstance(value, Exception) else SimpleNamespace(allow=lambda cap: value)
    manager._get_conn = Mock(side_effect=AssertionError("Forbidden write"))
    manager._db_lock = threading.RLock()
    manager.logger = Mock()
    manager.embedding_model = Mock()
    manager.faiss_index = Mock()
    assert manager.persist_interaction("research", "controlled", "answer") is None
    assert manager.store_fact({"content": "controlled"}) is None
    manager.index_message({"content": "controlled search response"})
    manager._save_faiss_index()
    manager._get_conn.assert_not_called()
    manager.embedding_model.encode.assert_not_called()
    manager.faiss_index.add.assert_not_called()


def test_sqlite_failure_is_not_privacy_denial(monkeypatch, writers):
    import core.privacy_gate as privacy
    monkeypatch.setattr(privacy, "get_privacy_gate", lambda: SimpleNamespace(allow=lambda cap: True))
    _, cache = writers
    conn = sqlite3.connect(str(cache.db_path))
    conn.execute("DROP TABLE artifacts")
    conn.commit()
    conn.close()
    with pytest.raises(sqlite3.OperationalError):
        cache.store(artifact())
    assert cache.get_hot_artifacts("test-window") == []


@pytest.mark.parametrize("content,memory", [(True, True), (False, True), (True, False), (False, False),
                                           (None, None), ("ALLOW", "ALLOW"), ("exception", "exception")])
def test_real_web_stream_keeps_volatile_answer(monkeypatch, writers, content, memory):
    import jarvis_web
    import core.privacy_gate as privacy
    from core.llm_router import ToolCallRequest
    from core.web_research import SearchOutcome
    events, cache = writers
    def allow(cap):
        if content == "exception":
            raise RuntimeError("controlled gate failure")
        return content if cap == Capability.CONTENT_LOGGING else memory
    monkeypatch.setattr(privacy, "get_privacy_gate", lambda *a: SimpleNamespace(allow=allow))
    monkeypatch.setattr("core.event_logger.get_event_logger", lambda: events)
    monkeypatch.setattr(jarvis_web, "get_interaction_cache", lambda: cache)
    monkeypatch.setattr("core.debug_logger.get_debug_logger", lambda: Mock())
    monkeypatch.setattr(jarvis_web, "_ensure_honorific_tail", lambda text: text)
    search = SimpleNamespace(search=Mock(return_value=SearchOutcome("success", [{"title": "Controlled", "url": "https://example.invalid", "snippet": "controlled snippet"}], backend="test")),
        fetch_pages_parallel=Mock(return_value=["controlled page"]), last_backend="test")
    llm = SimpleNamespace(tool_calling=True,
        stream_with_tools=lambda **kw: iter([ToolCallRequest(name="web_search", arguments={"query": "controlled query"}, call_id="test")]),
        continue_after_tool_call=lambda *a, **kw: iter(["Controlled answer."]),
        strip_filler=lambda text: text)
    state = SimpleNamespace(turn_count=1, window_id="stream-window")
    ws = SimpleNamespace(send_json=AsyncMock())
    response, streamed, image = asyncio.run(jarvis_web._stream_llm_ws(
        ws, llm, "controlled query", [], search, conv_state=state))
    assert response == "Controlled answer."
    assert streamed is True and image is None
    search.search.assert_called_once()
    assert events.count() == int(content is True)
    with sqlite3.connect(str(cache.db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == (2 if memory is True else 0)
    assert any(call.args[0].get("full_response") == response for call in ws.send_json.call_args_list)


@pytest.mark.parametrize("mode", ["normal", "privacy", "privacy_lock"])
def test_fake_provider_returns_results_without_content_logs(monkeypatch, caplog, mode):
    from core.web_research import WebResearcher
    import core.privacy_gate as privacy
    privacy.reset_privacy_gate_singleton_for_tests()
    gate = privacy.get_privacy_gate()
    if mode != "normal":
        gate.enter(privacy.PrivacyMode(mode), actor="test")
    monkeypatch.setenv("SERPER_API_KEY", "test-placeholder")
    researcher = WebResearcher()
    expected = [{"title": "Controlled", "url": "https://example.invalid", "snippet": "synthetic snippet"}]
    monkeypatch.setattr(researcher, "_search_serper", lambda *a: expected)
    with caplog.at_level("DEBUG"):
        assert researcher.search("controlled-query-marker").results == expected
        assert researcher.search("controlled-query-marker").results == expected
    assert "controlled-query-marker" not in caplog.text
    privacy.reset_privacy_gate_singleton_for_tests()


@pytest.mark.parametrize("failure", [False, None, "ALLOW", "exception", "lookup"])
def test_all_event_content_writers_fail_closed(monkeypatch, writers, failure):
    import core.privacy_gate as privacy
    events, _ = writers
    if failure == "lookup":
        monkeypatch.setattr(privacy, "get_privacy_gate", Mock(side_effect=RuntimeError("lookup failed")))
    else:
        gate = SimpleNamespace(allow=Mock(side_effect=RuntimeError("gate failed"))) if failure == "exception" else SimpleNamespace(allow=lambda cap: failure)
        monkeypatch.setattr(privacy, "get_privacy_gate", lambda: gate)
    assert events.add_score(observation_id="controlled", name="test", comment="controlled") is None
    assert events.add_reflection(category="strategy_update", content="controlled") is None
    assert events.capture_odd_event("controlled") is None
    events.store_health_snapshot({"test": {"value": 1, "detail": "controlled"}})
    with sqlite3.connect(str(events.db_path)) as conn:
        for table in ("observations", "scores", "reflections", "health_snapshots", "odd_events"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_memory_rechecks_after_embedding():
    import numpy as np
    from core.memory_manager import MemoryManager
    manager = MemoryManager.__new__(MemoryManager)
    manager.read_only = False
    allowed = [True]
    manager._privacy_gate = SimpleNamespace(allow=lambda cap: allowed[0])
    manager._get_conn = Mock(side_effect=AssertionError("Forbidden write"))
    manager._db_lock = threading.RLock()
    manager.logger = Mock()
    def encode(*a, **kw):
        allowed[0] = False
        return np.array([1, 0], dtype=np.float32)
    manager.embedding_model = SimpleNamespace(encode=encode)
    manager.persist_interaction("research", "controlled", "answer")
    manager._get_conn.assert_not_called()


def test_memory_interaction_allow_writes_once(tmp_path):
    from core.memory_manager import MemoryManager
    manager = MemoryManager.__new__(MemoryManager)
    manager.read_only = False
    manager._privacy_gate = SimpleNamespace(allow=lambda cap: True)
    manager._db_lock = threading.RLock()
    manager.logger = Mock()
    manager.embedding_model = None
    path = tmp_path / "memory.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE interaction_log (interaction_id, user_id, type, query, detail, answer_summary, metadata_json, created_at, embedding)")
    conn.close()
    manager._get_conn = lambda: sqlite3.connect(path)
    manager.persist_interaction("research", "controlled", "answer", metadata={"provider": "test"})
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT query, answer_summary FROM interaction_log").fetchall() == [("controlled", "answer")]


def test_cache_deny_blocks_mutations_of_existing_search(monkeypatch, writers):
    import core.privacy_gate as privacy
    _, cache = writers
    monkeypatch.setattr(privacy, "get_privacy_gate", lambda: SimpleNamespace(allow=lambda cap: True))
    cache.store(artifact())
    with sqlite3.connect(str(cache.db_path)) as conn:
        before = list(conn.iterdump())
    monkeypatch.setattr(privacy, "get_privacy_gate", lambda: SimpleNamespace(allow=lambda cap: False))
    cache.record_access("controlled-search", "rehydrate")
    cache.create_link("controlled-search", "other")
    cache.demote_window("test-window")
    assert cache.promote_window("test-window") == []
    assert cache.decompose("controlled-search", "test-window") == []
    assert cache.rehydrate(["controlled-search"], "other-window") == []
    cache.consolidate()
    with sqlite3.connect(str(cache.db_path)) as conn:
        assert list(conn.iterdump()) == before
