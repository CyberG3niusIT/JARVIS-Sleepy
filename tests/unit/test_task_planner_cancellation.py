"""Unit tests for session #8 agentic-audit open finding: TaskPlanner
previously could only cancel a plan BETWEEN steps
(_check_for_interrupt() at the top of the execute_plan() loop) — a
step already in flight always ran to completion regardless of a
cancel request, since the task explicitly rules out brutal thread
kills as the fix.

core/task_planner.py now exposes a cooperative cancellation token via
current_cancel_event()/_cancel_event_scope(): a threading.Event
published on the executing thread for the duration of
execute_plan(), which a genuinely interruptible tool MAY poll between
its own internal sub-steps to stop early. This is advisory only —
nothing that doesn't check it behaves any differently than before.

core/web_research.py's fetch_pages_parallel() is the first consumer:
it checks the event between processing each completed page fetch and
stops collecting further pages (still returning whatever was already
collected) once cancellation is requested.
"""

import concurrent.futures
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

import core.task_planner as task_planner
from core.task_planner import current_cancel_event, _cancel_event_scope


class TestCurrentCancelEventScope:
    def test_none_outside_any_scope(self):
        assert current_cancel_event() is None

    def test_returns_the_scoped_event_inside_the_with_block(self):
        evt = threading.Event()
        with _cancel_event_scope(evt):
            assert current_cancel_event() is evt
        assert current_cancel_event() is None

    def test_restores_previous_event_on_nested_exit(self):
        outer = threading.Event()
        inner = threading.Event()
        with _cancel_event_scope(outer):
            with _cancel_event_scope(inner):
                assert current_cancel_event() is inner
            assert current_cancel_event() is outer
        assert current_cancel_event() is None

    def test_is_thread_local(self):
        evt = threading.Event()
        seen_in_other_thread = []

        def worker():
            seen_in_other_thread.append(current_cancel_event())

        with _cancel_event_scope(evt):
            t = threading.Thread(target=worker)
            t.start()
            t.join()

        assert seen_in_other_thread == [None]


class _FakeConfig(dict):
    def get(self, path, default=None):
        return default


class _FakeSkillManager:
    pass


class _FakeSelfAwareness:
    pass


@pytest.fixture
def planner():
    return task_planner.TaskPlanner(
        llm=None,
        skill_manager=_FakeSkillManager(),
        self_awareness=_FakeSelfAwareness(),
        config=_FakeConfig({}),
    )


class TestPlannerCancelSetsCooperativeEvent:
    def test_cancel_event_starts_clear(self, planner):
        assert not planner._cancel_event.is_set()

    def test_cancel_sets_the_cooperative_event_when_plan_running(self, planner):
        plan = task_planner.TaskPlan(original_request="x", steps=[])
        plan.status = task_planner.PlanStatus.RUNNING
        planner.active_plan = plan

        planner.cancel()

        assert planner._cancel_event.is_set()
        assert planner._cancel_requested is True

    def test_cancel_is_a_noop_on_event_when_no_plan_running(self, planner):
        planner.active_plan = None
        planner.cancel()
        assert not planner._cancel_event.is_set()

    def test_current_cancel_event_visible_during_execute_plan(self, planner, monkeypatch):
        """The cooperative token must actually be published while a plan
        is executing, and cleared again once it finishes — verified via
        a fake single-step plan whose 'skill' just captures whether
        current_cancel_event() resolves to planner._cancel_event."""
        seen = []

        def fake_execute_step(step, prior_context):
            seen.append(current_cancel_event())
            return "done"

        monkeypatch.setattr(planner, "_execute_step", fake_execute_step)
        monkeypatch.setattr(planner, "_evaluate_step_result", lambda step, plan: ("continue", ""))

        plan = task_planner.TaskPlan(
            original_request="x",
            steps=[task_planner.PlanStep(step_id=1, description="test step",
                                          skill_name="noop", input_text="x")],
        )

        planner.execute_plan(plan)

        assert seen == [planner._cancel_event]
        # Cleaned up after execute_plan() returns.
        assert current_cancel_event() is None


class TestWebResearchStopsEarlyOnCancellation:
    """core/web_research.py fetch_pages_parallel() checks
    current_cancel_event() between processing each completed fetch."""

    def _fake_pool(self, monkeypatch, results_by_url: dict):
        """Monkeypatch ProcessPoolExecutor with a fake whose submit()
        returns already-resolved Futures, so the test never touches a
        real subprocess or the network."""
        import core.web_research as web_research

        class _FakePool:
            def submit(self, fn, url, *args):
                fut = concurrent.futures.Future()
                fut.set_result(results_by_url.get(url))
                return fut

            def shutdown(self, wait=True, cancel_futures=False):
                pass

        monkeypatch.setattr(web_research, "ProcessPoolExecutor", lambda max_workers: _FakePool())
        return web_research

    def test_stops_collecting_once_cancelled(self, monkeypatch):
        urls = [f"http://example.com/{i}" for i in range(5)]
        results = {u: (u, "x" * 500) for u in urls}
        web_research = self._fake_pool(monkeypatch, results)

        cancel_evt = threading.Event()
        cancel_evt.set()  # already cancelled before the fetch even starts
        monkeypatch.setattr(task_planner, "current_cancel_event", lambda: cancel_evt)

        researcher = web_research.WebResearcher.__new__(web_research.WebResearcher)
        researcher.logger = web_research.get_logger("test.web_research")
        researcher._page_cache = web_research._TTLCache(ttl_seconds=60)
        researcher.last_backend = "ddg"

        results_in = [{"title": f"T{i}", "url": u, "snippet": ""} for i, u in enumerate(urls)]
        sections = researcher.fetch_pages_parallel(results_in, max_results=5, timeout=5.0)

        assert sections == []  # cancelled before any page was accepted

    def test_collects_normally_when_not_cancelled(self, monkeypatch):
        urls = [f"http://example.com/{i}" for i in range(3)]
        results = {u: (u, "y" * 500) for u in urls}
        web_research = self._fake_pool(monkeypatch, results)

        cancel_evt = threading.Event()  # never set
        monkeypatch.setattr(task_planner, "current_cancel_event", lambda: cancel_evt)

        researcher = web_research.WebResearcher.__new__(web_research.WebResearcher)
        researcher.logger = web_research.get_logger("test.web_research")
        researcher._page_cache = web_research._TTLCache(ttl_seconds=60)
        researcher.last_backend = "ddg"

        results_in = [{"title": f"T{i}", "url": u, "snippet": ""} for i, u in enumerate(urls)]
        sections = researcher.fetch_pages_parallel(results_in, max_results=5, timeout=5.0)

        assert len(sections) == 3
