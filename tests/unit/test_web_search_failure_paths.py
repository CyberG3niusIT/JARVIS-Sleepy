"""Synthetic provider failures through real callers; no network or audio."""
import asyncio
import sqlite3
import threading
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from core.llm_router import ToolCallRequest
from core.web_research import SearchOutcome


FAILURE_STATUSES = (
    "empty", "dependency_missing", "provider_unavailable", "error",
    "invalid_query", "timeout",
)
QUERY = "synthetic-private-query-marker"


def fake_search(status):
    return SimpleNamespace(
        search=Mock(return_value=SearchOutcome(status, [], backend="test")),
        fetch_pages_parallel=Mock(side_effect=AssertionError("No data to fetch")),
        last_backend="test",
    )


def fake_llm():
    return SimpleNamespace(
        tool_calling=True,
        stream_with_tools=Mock(side_effect=lambda **kw: iter([
            ToolCallRequest("web_search", {"query": QUERY}, call_id="test"),
        ])),
        continue_after_tool_call=Mock(side_effect=AssertionError("Unbacked synthesis")),
        chat=Mock(side_effect=AssertionError("Unbacked fallback")),
        strip_filler=lambda text: text,
    )


@pytest.fixture
def harmless_runtime(monkeypatch):
    import jarvis_web
    monkeypatch.setattr("core.debug_logger.get_debug_logger", lambda: Mock())
    monkeypatch.setattr(jarvis_web, "_ensure_honorific_tail", lambda text: text)
    events = Mock()
    monkeypatch.setattr("core.event_logger.get_event_logger", lambda: events)
    cache = Mock()
    monkeypatch.setattr(jarvis_web, "get_interaction_cache", lambda: cache)
    return events, cache


@pytest.mark.parametrize("status", FAILURE_STATUSES)
@pytest.mark.parametrize("path", ("stream", "fallback", "deflection"))
def test_web_failures_never_synthesize(monkeypatch, harmless_runtime, status, path):
    import jarvis_web
    events, cache = harmless_runtime
    search, llm = fake_search(status), fake_llm()
    expected = search.search.return_value.failure_message
    if path == "stream":
        ws = SimpleNamespace(send_json=AsyncMock())
        state = SimpleNamespace(turn_count=1, window_id="failure-test")
        response, streamed, image = asyncio.run(jarvis_web._stream_llm_ws(
            ws, llm, QUERY, [], search, conv_state=state))
        assert streamed is True and image is None
        assert any(call.args[0].get("full_response") == expected
                   for call in ws.send_json.call_args_list)
    elif path == "fallback":
        response = asyncio.run(jarvis_web._llm_fallback(llm, QUERY, [], search))
    else:
        response = asyncio.run(jarvis_web._do_web_search(QUERY, search, llm))
    assert response == expected
    search.fetch_pages_parallel.assert_not_called()
    llm.continue_after_tool_call.assert_not_called()
    llm.chat.assert_not_called()
    cache.store.assert_not_called()
    if path != "deflection":
        events.emit.assert_called_once()
        assert events.emit.call_args.kwargs["status"] == search.search.return_value.event_status
    for call in events.emit.call_args_list:
        assert call.kwargs.get("status") != "success"


@pytest.mark.parametrize("status", FAILURE_STATUSES)
def test_voice_failures_never_synthesize(monkeypatch, harmless_runtime, status):
    from core.pipeline import Coordinator
    class Timer:
        def __init__(self, *args, **kwargs):
            pass
        def start(self):
            pass
        def cancel(self):
            pass
    monkeypatch.setattr("core.pipeline.threading.Timer", Timer)
    events, cache = harmless_runtime
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.conversation = SimpleNamespace(current_user="test-owner")
    coordinator.conv_state = SimpleNamespace(jarvis_asked_question=False)
    coordinator._classify_ack = lambda *a, **kw: ("none", None)
    coordinator._play_ack_if_still_thinking = Mock()
    coordinator._turn_cancelled = threading.Event()
    coordinator._current_latency = None
    coordinator.logger = Mock()
    coordinator.tts = SimpleNamespace(engine="piper")
    coordinator.listener = SimpleNamespace(active_tts_text="")
    coordinator.web_researcher = fake_search(status)
    coordinator.llm = fake_llm()
    coordinator.interaction_cache = cache
    coordinator._speak_and_wait = Mock()
    response = coordinator._stream_llm_response(QUERY, "")
    assert response == coordinator.web_researcher.search.return_value.failure_message
    coordinator.web_researcher.fetch_pages_parallel.assert_not_called()
    coordinator.llm.continue_after_tool_call.assert_not_called()
    coordinator.llm.chat.assert_not_called()
    cache.store.assert_not_called()
    events.emit.assert_called_once()
    assert events.emit.call_args.kwargs["status"] == coordinator.web_researcher.search.return_value.event_status
    for call in events.emit.call_args_list:
        assert call.kwargs.get("status") != "success"


@pytest.mark.parametrize("status", FAILURE_STATUSES)
def test_planner_failures_never_use_parametric_knowledge(status):
    from core.task_planner import TaskPlanner
    planner = TaskPlanner.__new__(TaskPlanner)
    planner._web_researcher = fake_search(status)
    planner._llm = fake_llm()
    planner._llm_synthesis = Mock(side_effect=AssertionError("Unbacked fallback"))
    response = planner._web_research(QUERY, SimpleNamespace())
    # The existing planner treats any nonempty response as a completed step.
    assert response == ""
    planner._web_researcher.fetch_pages_parallel.assert_not_called()
    planner._llm_synthesis.assert_not_called()
    planner._llm.chat.assert_not_called()


def test_plan_search_failure_marks_failed_and_skips_dependent_step(monkeypatch):
    from core.task_planner import TaskPlanner, TaskPlan, PlanStep, StepStatus, PlanStatus
    monkeypatch.setattr("core.debug_logger.get_debug_logger", lambda: Mock())
    planner = TaskPlanner(llm=fake_llm(), skill_manager=Mock(),
                          self_awareness=Mock(), web_researcher=fake_search("error"))
    planner._check_for_interrupt = lambda: None
    planner._llm_synthesis = Mock(side_effect=AssertionError("Unbacked knowledge"))
    planner._evaluate_step_result = Mock(side_effect=AssertionError("Failed step evaluation"))
    plan = TaskPlan(QUERY, steps=[
        PlanStep(1, "Public research", "web_research", QUERY),
        PlanStep(2, "Dependent document", "create_document", "synthetic report"),
    ])
    response = planner.execute_plan(plan)
    assert plan.status == PlanStatus.FAILED
    assert plan.steps[0].status == StepStatus.FAILED
    assert plan.steps[1].status == StepStatus.SKIPPED
    assert "keinen der Schritte" in response
    planner._llm.chat.assert_not_called()
    planner._llm_synthesis.assert_not_called()
    planner._evaluate_step_result.assert_not_called()


@pytest.mark.parametrize("status", FAILURE_STATUSES)
def test_research_document_failure_creates_nothing(status, caplog):
    from skills.system.file_editor.skill import FileEditorSkill
    skill = FileEditorSkill.__new__(FileEditorSkill)
    skill.logger = logging.getLogger("jarvis.file_editor_failure_test")
    skill._web_researcher = fake_search(status)
    skill._generate_structure = Mock(side_effect=AssertionError("Unbacked document"))
    with caplog.at_level("DEBUG"):
        response = skill._generate_document({"topic": QUERY, "research_needed": True})
    assert "Das Dokument wurde nicht erstellt" in response
    skill._web_researcher.fetch_pages_parallel.assert_not_called()
    skill._generate_structure.assert_not_called()
    assert QUERY not in caplog.text


def test_failure_denied_writers_do_not_persist_sensitive_data(monkeypatch, tmp_path, caplog):
    import jarvis_web
    import core.privacy_gate as privacy
    from core.event_logger import EventLogger
    from core.interaction_cache import InteractionCache
    gate = SimpleNamespace(allow=lambda capability: False)
    monkeypatch.setattr(privacy, "get_privacy_gate", lambda *a: gate)
    events = EventLogger({"events.db_path": str(tmp_path / "events.db")})
    cache = InteractionCache({"system.storage_path": str(tmp_path)})
    monkeypatch.setattr("core.event_logger.get_event_logger", lambda: events)
    monkeypatch.setattr(jarvis_web, "get_interaction_cache", lambda: cache)
    monkeypatch.setattr("core.debug_logger.get_debug_logger", lambda: Mock())
    ws = SimpleNamespace(send_json=AsyncMock())
    search = fake_search("error")
    with caplog.at_level("DEBUG"):
        response, _, _ = asyncio.run(jarvis_web._stream_llm_ws(
            ws, fake_llm(), QUERY, [], search,
            conv_state=SimpleNamespace(turn_count=1, window_id="denied")))
    assert response == search.search.return_value.failure_message
    assert QUERY not in caplog.text
    assert events.count() == 0
    with sqlite3.connect(str(cache.db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0
    assert cache.get_hot_artifacts("denied") == []


@pytest.mark.parametrize("path", ("fallback", "deflection", "planner"))
def test_usable_search_data_reaches_success_synthesis(harmless_runtime, path):
    import jarvis_web
    from core.task_planner import TaskPlanner
    results = [{"title": "Synthetic evidence", "url": "https://example.invalid/data",
                "snippet": "synthetic-backed-fact-marker"}]
    search = SimpleNamespace(search=Mock(return_value=SearchOutcome("success", results, backend="test")),
                             fetch_pages_parallel=Mock(return_value=[]))
    llm = fake_llm()
    llm.continue_after_tool_call = Mock(side_effect=lambda *a, **kw: iter(["Backed synthetic answer."]))
    llm.chat = Mock(return_value="Backed synthetic answer.")
    if path == "fallback":
        response = asyncio.run(jarvis_web._llm_fallback(llm, QUERY, [], search))
        assert results[0]["snippet"] in llm.continue_after_tool_call.call_args.args[1]
    elif path == "deflection":
        response = asyncio.run(jarvis_web._do_web_search(QUERY, search, llm))
        assert results[0]["snippet"] in llm.chat.call_args.kwargs["user_message"]
    else:
        planner = TaskPlanner(llm=llm, skill_manager=Mock(), self_awareness=Mock(), web_researcher=search)
        response = planner._web_research(QUERY, SimpleNamespace())
        assert results[0]["snippet"] in llm.chat.call_args.kwargs["user_message"]
    assert response == "Backed synthetic answer."
    search.fetch_pages_parallel.assert_called_once()
