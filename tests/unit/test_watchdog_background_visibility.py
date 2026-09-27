"""Unit tests for session #8 agentic-audit open finding: Watchdog had
zero visibility outside the voice pipeline itself — a dead
reminder/weather/news poll thread, or a TaskPlanner step stuck
mid-execution, went completely unnoticed. Watchdog now optionally
accepts task_planner/reminder_manager/weather_poller/news_manager
references (all default None, so existing call sites keep working
unchanged) and detects (never auto-restarts/cancels) dead or stale
poll threads and stuck plan steps.

Constructs Watchdog via bare __new__() + manually set attributes
(matching this codebase's established pattern for classes with heavy
__init__ dependencies) so these tests never need a real coordinator/
listener/tts/audio pipeline.
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.watchdog import Watchdog


def _bare_watchdog(**managers) -> Watchdog:
    wd = Watchdog.__new__(Watchdog)
    wd.logger = __import__("core.logger", fromlist=["get_logger"]).get_logger("test.watchdog")
    wd._task_planner = managers.get("task_planner")
    wd._background_managers = {
        name: mgr for name, mgr in {
            "reminder_manager": managers.get("reminder_manager"),
            "weather_poller": managers.get("weather_poller"),
            "news_manager": managers.get("news_manager"),
        }.items() if mgr is not None
    }
    wd._poll_stuck_multiplier = 3
    wd._command_hung_threshold = 120
    wd._worker_status = {}
    wd._plan_step_seen = None
    wd._plan_stuck_logged = False
    wd._recovery_log = {}

    emitted = []
    wd._emit_event = lambda *a, **k: emitted.append((a, k))
    wd._emitted = emitted
    return wd


class _FakeManager:
    def __init__(self, alive=True, last_poll_ts=None, poll_interval=30):
        class _FakeThread:
            def __init__(self, alive):
                self._alive = alive

            def is_alive(self):
                return self._alive

        self._poll_thread = _FakeThread(alive)
        self._last_poll_ts = last_poll_ts if last_poll_ts is not None else time.time()
        self.poll_interval = poll_interval


class TestDeadWorkerDetection:
    def test_never_started_worker_is_not_flagged(self):
        mgr = _FakeManager()
        mgr._poll_thread = None
        wd = _bare_watchdog(news_manager=mgr)

        wd._check_background_workers()

        assert wd._worker_status == {}
        assert wd._emitted == []

    def test_dead_thread_is_detected_and_emitted(self):
        mgr = _FakeManager(alive=False)
        wd = _bare_watchdog(news_manager=mgr)

        wd._check_background_workers()

        assert wd._worker_status["news_manager"] == "dead"
        assert len(wd._emitted) == 1
        assert wd._emitted[0][1]["metadata"]["status"] == "dead"

    def test_healthy_thread_is_not_emitted(self):
        mgr = _FakeManager(alive=True, last_poll_ts=time.time(), poll_interval=30)
        wd = _bare_watchdog(weather_poller=mgr)

        wd._check_background_workers()

        assert wd._worker_status["weather_poller"] == "healthy"
        assert wd._emitted == []

    def test_stale_poll_is_detected_as_stuck(self):
        mgr = _FakeManager(alive=True, last_poll_ts=time.time() - 1000, poll_interval=30)
        wd = _bare_watchdog(reminder_manager=mgr)

        wd._check_background_workers()

        assert wd._worker_status["reminder_manager"] == "stuck"
        assert wd._emitted[0][1]["metadata"]["status"] == "stuck"

    def test_recovery_transition_is_logged_once(self):
        mgr = _FakeManager(alive=False)
        wd = _bare_watchdog(news_manager=mgr)
        wd._check_background_workers()
        assert wd._worker_status["news_manager"] == "dead"

        mgr._poll_thread._alive = True
        mgr._last_poll_ts = time.time()
        wd._check_background_workers()

        assert wd._worker_status["news_manager"] == "healthy"

    def test_status_unchanged_does_not_re_emit(self):
        mgr = _FakeManager(alive=False)
        wd = _bare_watchdog(news_manager=mgr)
        wd._check_background_workers()
        wd._check_background_workers()
        wd._check_background_workers()

        assert len(wd._emitted) == 1  # only the first transition into "dead"

    def test_multiple_managers_tracked_independently(self):
        dead = _FakeManager(alive=False)
        healthy = _FakeManager(alive=True)
        wd = _bare_watchdog(news_manager=dead, weather_poller=healthy)

        wd._check_background_workers()

        assert wd._worker_status == {"news_manager": "dead", "weather_poller": "healthy"}


class _FakeStep:
    def __init__(self, step_id, status, description="step", skill_name="skill"):
        self.step_id = step_id
        self.status = status
        self.description = description
        self.skill_name = skill_name


class _FakeStatus:
    def __init__(self, value):
        self.value = value


class _FakePlan:
    def __init__(self, steps, status="running"):
        self.steps = steps
        self.status = _FakeStatus(status)


class _FakeTaskPlanner:
    def __init__(self, active_plan=None):
        self.active_plan = active_plan


class TestTaskPlannerStuckDetection:
    def test_no_task_planner_is_a_noop(self):
        wd = _bare_watchdog()
        wd._check_task_planner_stuck()
        assert wd._emitted == []

    def test_no_active_plan_is_a_noop(self):
        wd = _bare_watchdog(task_planner=_FakeTaskPlanner(active_plan=None))
        wd._check_task_planner_stuck()
        assert wd._emitted == []
        assert wd._plan_step_seen is None

    def test_first_observation_of_running_step_does_not_flag(self):
        plan = _FakePlan([_FakeStep(1, _FakeStatus("running"))])
        tp = _FakeTaskPlanner(active_plan=plan)
        wd = _bare_watchdog(task_planner=tp)

        wd._check_task_planner_stuck()

        assert wd._plan_step_seen is not None
        assert wd._emitted == []

    def test_step_stuck_past_threshold_is_flagged(self, monkeypatch):
        plan = _FakePlan([_FakeStep(1, _FakeStatus("running"))])
        tp = _FakeTaskPlanner(active_plan=plan)
        wd = _bare_watchdog(task_planner=tp)
        wd._command_hung_threshold = 5

        # First check establishes the baseline timestamp.
        wd._check_task_planner_stuck()
        assert wd._emitted == []

        # Simulate time passing past the threshold without the step changing.
        import core.watchdog as watchdog_module
        real_monotonic = time.monotonic
        monkeypatch.setattr(watchdog_module.time, "monotonic", lambda: real_monotonic() + 10)

        wd._check_task_planner_stuck()

        assert len(wd._emitted) == 1
        assert wd._emitted[0][1]["metadata"]["step_id"] == 1

    def test_step_completing_resets_stuck_tracking(self):
        step = _FakeStep(1, _FakeStatus("running"))
        plan = _FakePlan([step])
        tp = _FakeTaskPlanner(active_plan=plan)
        wd = _bare_watchdog(task_planner=tp)

        wd._check_task_planner_stuck()
        step.status = _FakeStatus("completed")
        wd._check_task_planner_stuck()

        assert wd._plan_step_seen is None
        assert wd._plan_stuck_logged is False

    def test_different_step_resets_the_baseline(self):
        plan = _FakePlan([_FakeStep(1, _FakeStatus("completed")),
                          _FakeStep(2, _FakeStatus("running"))])
        tp = _FakeTaskPlanner(active_plan=plan)
        wd = _bare_watchdog(task_planner=tp)

        wd._check_task_planner_stuck()
        first_key = wd._plan_step_seen[0]
        assert first_key[1] == 2


class TestGetBackgroundHealth:
    def test_snapshot_reflects_worker_and_plan_state(self):
        mgr = _FakeManager(alive=False)
        step = _FakeStep(1, _FakeStatus("running"))
        plan = _FakePlan([step])
        tp = _FakeTaskPlanner(active_plan=plan)
        wd = _bare_watchdog(news_manager=mgr, task_planner=tp)

        wd._check_background_workers()
        health = wd.get_background_health()

        assert health["workers"]["news_manager"] == "dead"
        assert health["task_planner"]["running_step_id"] == 1
        assert health["task_planner"]["status"] == "running"
