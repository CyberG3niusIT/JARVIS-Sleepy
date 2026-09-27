"""Primary <-> Expert handover: state order, mutex, rollback, honest status (all with fakes).

No real systemctl, llama-server or GPU is touched: ``systemctl``, ``health``, ``port_listening``,
``clock`` and ``sleep`` are injected.
"""

import os
import threading
import time

import pytest

from core import runtime_state
from core.model_handover import HandoverState, ModelHandover

P, E = "llama-server-primary.service", "llama-server-expert.service"


class FakeSystem:
    """Fake user-scope systemd + health/port facts. Records every call with the handover state."""

    def __init__(self, active=(P,)):
        self.active = set(active)
        self.log = []                 # (action, unit, handover_state)
        self.violations = []          # start while the other unit is active
        self.max_active = len(self.active)
        self.stop_fails = set()       # units whose stop is ineffective
        self.start_fails = set()
        self.healthy = {"primary": True, "expert": True}
        self.gates = {"primary": threading.Event(), "expert": threading.Event()}
        self.gates["primary"].set()
        self.gates["expert"].set()
        self.handover = None
        self.now = 0.0

    def _state(self):
        return self.handover.state.value if self.handover else "?"

    def systemctl(self, action, unit):
        self.log.append((action, unit, self._state()))
        if action == "is-active":
            return 0, "active" if unit in self.active else "inactive"
        if action == "stop":
            if unit not in self.stop_fails:
                self.active.discard(unit)
            return 0, ""
        if action == "start":
            other = E if unit == P else P
            if other in self.active:
                self.violations.append((unit, other))
            if unit in self.start_fails:
                return 1, "failed"
            self.active.add(unit)
            self.max_active = max(self.max_active, len(self.active))
            return 0, ""
        raise AssertionError(f"unexpected systemctl {action}")

    def health(self, role):
        unit = P if role == "primary" else E
        return unit in self.active and self.healthy[role] and self.gates[role].is_set()

    def port_listening(self, role):
        return (P if role == "primary" else E) in self.active

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        time.sleep(0.001)

    def calls(self, action, unit=None):
        return [(a, u, s) for a, u, s in self.log if a == action and (unit is None or u == unit)]


CONFIG = {
    "handover.stop_timeout_s": 5,
    "handover.primary_start_timeout_s": 100000,
    "handover.expert_start_timeout_s": 100000,
    "handover.vram_release_wait_s": 2,
    "handover.poll_interval_s": 1,
}


class Cfg:
    def __init__(self, values=None):
        self.values = dict(CONFIG, **(values or {}))

    def get(self, key, default=None):
        return self.values.get(key, default)


def make(tmp_path, monkeypatch, *, active=(P,), fallback=None, **cfg):
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path))
    system = FakeSystem(active)
    handover = ModelHandover(
        Cfg(cfg), systemctl=system.systemctl, health=system.health, port_listening=system.port_listening,
        clock=system.clock, sleep=system.sleep, fallback_available=fallback, state_dir=tmp_path,
    )
    system.handover = handover
    return handover, system


def run(handover, call=lambda task: f"expert:{task}", save=lambda: {"turns": ["hi"]}, restore=lambda snap: None):
    result = handover.run_expert("task", call, save, restore)
    assert handover.join_restore(10)
    return result


def test_state_transitions_happen_in_the_specified_order(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    seen = []

    def call(task):
        seen.append(handover.state)
        return "answer"

    result = run(handover, call=call)
    assert result.ok and result.answer == "answer"
    assert seen == [HandoverState.EXPERT_RUNNING]
    assert system.calls("stop", P)[0][2] == "STOPPING_PRIMARY"
    assert system.calls("start", E)[0][2] == "STARTING_EXPERT"
    assert system.calls("stop", E)[0][2] == "STOPPING_EXPERT"
    assert system.calls("start", P)[0][2] == "RESTORING_PRIMARY"
    order = [(a, u) for a, u, _ in system.log if a in ("start", "stop")]
    assert order == [("stop", P), ("start", E), ("stop", E), ("start", P)]
    assert handover.state is HandoverState.IDLE
    assert handover.lifecycle_state() == "READY"


def test_never_both_units_active_and_expert_needs_verified_primary_stop(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    run(handover)
    assert system.violations == []
    assert system.max_active == 1
    assert system.active == {P}


def test_expert_is_not_started_when_primary_stop_cannot_be_verified(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    system.stop_fails.add(P)
    result = run(handover)
    assert not result.ok and result.error == "primary_stop_not_verified"
    assert system.calls("start", E) == []
    assert system.active == {P}          # the primary was never taken down and stays as is
    assert handover.lifecycle_state() == "READY"


def test_primary_is_restored_when_the_expert_call_fails(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)

    def boom(task):
        raise RuntimeError("oom")

    result = run(handover, call=boom)
    assert not result.ok and result.error.startswith("expert_call_failed")
    assert system.active == {P} and system.violations == []
    assert handover.lifecycle_state() == "READY"


@pytest.mark.parametrize("failure", ["start_fails", "unhealthy"])
def test_primary_is_restored_when_the_expert_does_not_come_up(tmp_path, monkeypatch, failure):
    handover, system = make(tmp_path, monkeypatch, **{"handover.expert_start_timeout_s": 3})
    if failure == "start_fails":
        system.start_fails.add(E)
    else:
        system.healthy["expert"] = False
    result = run(handover)
    assert not result.ok
    assert result.error in ("expert_start_failed", "expert_health_timeout")
    assert system.active == {P} and system.violations == []
    assert system.calls("stop", E)                     # a half-started expert is always cleaned up


def test_failed_primary_restore_is_reported_honestly(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    system.start_fails.add(P)
    result = run(handover)
    assert result.ok                                    # the expert answer itself is valid
    assert handover.state is HandoverState.IDLE
    assert handover.lifecycle_state() == "ERROR"
    assert handover.status()["primary_ready"] is False
    assert "primary_start_failed" in handover.status()["error"]
    assert runtime_state.read_lifecycle(tmp_path)["result"] == "ERROR"


def test_primary_health_timeout_is_degraded_not_ready(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch, **{"handover.primary_start_timeout_s": 3})
    system.healthy["primary"] = False
    run(handover)
    assert handover.lifecycle_state() == "DEGRADED"
    assert handover.status()["primary_ready"] is False


def test_primary_is_not_started_while_the_expert_cannot_be_verified_gone(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    system.stop_fails.add(E)
    result = run(handover)
    assert not result.ok and result.error == "expert_stop_not_verified"
    assert system.calls("start", P) == []              # mutex: never a second large model
    assert system.violations == []
    assert handover.lifecycle_state() == "ERROR"


def test_conversation_state_is_saved_before_and_restored_after_primary_is_back(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    events = []
    snapshot = {"turns": ["a", "b"]}

    def save():
        events.append(("save", handover.state.value, P in system.active))
        return snapshot

    def restore(snap):
        events.append(("restore", snap, P in system.active, handover.primary_ready))

    run(handover, save=save, restore=restore)
    assert events[0] == ("save", "SAVING_STATE", True)         # saved while the primary still runs
    assert events[1][0] == "restore" and events[1][1] is snapshot
    assert events[1][2] is True                                  # primary is back when state is restored


def test_failing_save_aborts_before_the_primary_is_touched(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)

    def save():
        raise ValueError("nope")

    result = run(handover, save=save)
    assert not result.ok and result.error == "save_state_failed"
    assert system.calls("stop") == [] and system.calls("start") == []


def test_expert_answer_is_returned_before_primary_is_ready(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    system.gates["primary"].clear()                # primary model "loads" until we open the gate
    result = handover.run_expert("task", lambda t: "spoken answer", lambda: None, lambda s: None)
    try:
        assert result.ok and result.answer == "spoken answer"
        assert result.primary_restore_started
        assert handover.last_answer == "spoken answer"
        status = handover.status()
        assert status["state"] == "RESTORING_PRIMARY" and status["restoring_primary"]
        assert status["lifecycle"] == "STARTING" and status["primary_ready"] is False
        assert handover.is_swapping
    finally:
        system.gates["primary"].set()
    assert handover.join_restore(10)
    assert handover.status()["lifecycle"] == "READY"


def test_requests_during_primary_starting_wait_honestly_without_fake_fallback(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    system.gates["primary"].clear()
    handover.run_expert("t", lambda t: "x", None, None)
    try:
        assert handover.wait_primary_ready(0.05) is False
        decision = handover.resolve_provider(0.05)
        assert decision.provider == "unavailable"          # nothing configured -> no fallback
        assert decision.status == "STARTING"
        assert decision.reason == "primary_not_ready_no_fallback"
    finally:
        system.gates["primary"].set()
    assert handover.join_restore(10)
    assert handover.resolve_provider(1).provider == "primary"


def test_a_waiting_request_is_released_when_the_primary_is_ready(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    system.gates["primary"].clear()
    handover.run_expert("t", lambda t: "x", None, None)
    outcome = []
    waiter = threading.Thread(target=lambda: outcome.append(handover.wait_primary_ready(10)))
    waiter.start()
    time.sleep(0.05)
    assert waiter.is_alive()                               # queued, not answered by anything else
    system.gates["primary"].set()
    waiter.join(10)
    assert outcome == [True]


def test_fallback_is_used_only_when_really_configured_and_available(tmp_path, monkeypatch):
    calls = []

    def fallback():
        calls.append(1)
        return True

    handover, system = make(tmp_path, monkeypatch, fallback=fallback)
    assert handover.resolve_provider(0.01).provider == "primary"
    assert calls == []                                      # never consulted while the primary is fine
    system.gates["primary"].clear()
    handover.run_expert("t", lambda t: "x", None, None)
    try:
        assert handover.resolve_provider(0.05).provider == "fallback"
    finally:
        system.gates["primary"].set()
        handover.join_restore(10)

    handover2, system2 = make(tmp_path, monkeypatch, fallback=lambda: False)
    system2.gates["primary"].clear()
    handover2.run_expert("t", lambda t: "x", None, None)
    try:
        assert handover2.resolve_provider(0.05).provider == "unavailable"
    finally:
        system2.gates["primary"].set()
        handover2.join_restore(10)


def test_phase_timings_are_recorded_and_logged_as_handover_lifecycle(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    live = []
    result = run(handover, call=lambda t: live.append(runtime_state.handover_in_progress(tmp_path)) or "ok")
    for phase in ("save_state", "stop_primary", "vram_release_wait", "start_expert", "expert_call",
                  "stop_expert", "restore_primary"):
        assert phase in handover.status()["timings"], phase
    assert handover.status()["timings"]["vram_release_wait"] >= 2     # the configured settle time
    assert result.timings["stop_primary"] >= 0
    assert live[0] is not None and live[0]["is_swapping"]              # visible to probe/watchdog
    record = runtime_state.read_lifecycle(tmp_path)
    assert record["action"] == "handover" and record["phase"] == "finished" and record["result"] == "READY"
    assert "restore_primary=" in record["message"]
    assert runtime_state.handover_in_progress(tmp_path) is None        # finished: no longer swapping


def test_expert_is_started_only_on_explicit_escalation(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    assert handover.status()["state"] == "IDLE"
    assert handover.lifecycle_state() == "READY"
    assert [c for c in system.log if c[0] in ("start", "stop")] == []   # constructing/observing never swaps


def test_second_handover_is_refused_while_one_runs(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)
    system.gates["primary"].clear()
    handover.run_expert("t", lambda t: "x", None, None)
    try:
        assert handover.run_expert("t2", lambda t: "y", None, None).error == "handover_busy"
    finally:
        system.gates["primary"].set()
        handover.join_restore(10)
    assert len(system.calls("start", E)) == 1


# -- hardening: TTL probe, reconcile, heartbeat/pid, fail-fast health, separate lifecycle record --

def test_primary_ready_is_reprobed_after_the_ttl_and_clears_the_error(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch, **{"llm.primary.health_ttl_s": 5})
    system.healthy["primary"] = False
    assert handover.primary_ready is False            # cached False ...
    system.healthy["primary"] = True
    assert handover.primary_ready is False            # ... inside the TTL
    handover._error, handover._fatal = "primary_health_timeout: x", True
    system.now += 6
    assert handover.primary_ready is True             # re-probed once the TTL is over
    assert handover.status()["error"] == "" and handover.lifecycle_state() == "READY"


def test_wait_health_fails_fast_when_the_unit_failed(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch, **{"handover.expert_start_timeout_s": 100000})
    orig = system.systemctl

    def failing_expert(action, unit):
        if action == "start" and unit == E:
            system.log.append((action, unit, system._state()))
            return 0, ""                               # start "succeeds" but the unit never becomes active
        return orig(action, unit)

    handover._systemctl = failing_expert
    result = run(handover)
    assert not result.ok and result.error == "expert_unit_failed"
    assert system.now < 100                             # did not wait out the 100000 s timeout
    assert system.active == {P}


def _crash_record(tmp_path, pid, swapping=True):
    runtime_state.write_handover({"state": "EXPERT_RUNNING", "is_swapping": swapping, "pid": pid}, tmp_path)


def test_dead_pid_or_stale_heartbeat_is_not_a_handover_in_progress(tmp_path):
    _crash_record(tmp_path, os.getpid())
    assert runtime_state.handover_in_progress(tmp_path) is not None
    _crash_record(tmp_path, 2 ** 22 + 12345)            # no such process
    assert runtime_state.handover_in_progress(tmp_path) is None
    assert runtime_state.stale_handover(tmp_path) is not None
    _crash_record(tmp_path, os.getpid())
    real = time.time
    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(runtime_state.time, "time", lambda: real() + runtime_state.HANDOVER_MAX_AGE_S + 5)
        assert runtime_state.handover_in_progress(tmp_path) is None
    finally:
        monkey.undo()


def test_heartbeat_refreshes_the_record_during_the_swap(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch, **{"handover.heartbeat_s": 0.01})
    gate = threading.Event()
    seen = []

    def call(task):
        first = runtime_state.read_handover(tmp_path)["updatedEpoch"]
        deadline = time.time() + 3
        while time.time() < deadline and runtime_state.read_handover(tmp_path)["updatedEpoch"] == first:
            time.sleep(0.01)
        seen.append(runtime_state.read_handover(tmp_path))
        return "ok"

    run(handover, call=call)
    assert seen[0]["pid"] == os.getpid() and seen[0]["state"] == "EXPERT_RUNNING"
    assert seen[0]["updatedEpoch"] > 0 and gate is not None


def test_reconcile_stops_a_stray_expert_and_restores_the_primary(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path))
    system = FakeSystem(active=(E,))                     # crashed while EXPERT_RUNNING
    _crash_record(tmp_path, 2 ** 22 + 999)
    handover = ModelHandover(Cfg(), systemctl=system.systemctl, health=system.health,
                             port_listening=system.port_listening, clock=system.clock, sleep=system.sleep,
                             state_dir=tmp_path)
    system.handover = handover
    assert handover.reconcile() == "restore_primary"
    assert handover.join_restore(10)
    assert system.active == {P} and system.violations == []
    order = [(a, u) for a, u, _ in system.log if a in ("start", "stop")]
    assert order == [("stop", E), ("start", P)]
    assert handover.lifecycle_state() == "READY"
    assert runtime_state.handover_in_progress(tmp_path) is None


def test_reconcile_leaves_a_live_or_healthy_state_alone(tmp_path, monkeypatch):
    handover, system = make(tmp_path, monkeypatch)       # healthy resting state
    assert handover.reconcile() == "none"
    assert [c for c in system.log if c[0] in ("start", "stop")] == []
    system2 = FakeSystem(active=(E,))
    runtime_state.write_handover({"state": "EXPERT_RUNNING", "is_swapping": True, "pid": os.getppid()}, tmp_path)
    other = ModelHandover(Cfg(), systemctl=system2.systemctl, health=system2.health,
                          port_listening=system2.port_listening, clock=system2.clock, sleep=system2.sleep,
                          state_dir=tmp_path)
    if runtime_state.handover_in_progress(tmp_path):     # another live owner: never interfere
        assert other.reconcile() == "live_handover"
        assert system2.calls("stop") == []


def test_reconcile_reports_an_expert_that_cannot_be_stopped(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path))
    system = FakeSystem(active=(E,))
    system.stop_fails.add(E)
    handover = ModelHandover(Cfg(), systemctl=system.systemctl, health=system.health,
                             port_listening=system.port_listening, clock=system.clock, sleep=system.sleep,
                             state_dir=tmp_path)
    system.handover = handover
    assert handover.reconcile() == "expert_stop_failed"
    assert system.calls("start", P) == []                # mutex: no second large model
    assert handover.lifecycle_state() == "ERROR"


def test_construction_never_reconciles_unless_asked(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path))
    system = FakeSystem(active=(E,))
    ModelHandover(Cfg(), systemctl=system.systemctl, health=system.health, port_listening=system.port_listening,
                  clock=system.clock, sleep=system.sleep, state_dir=tmp_path)
    assert system.calls("stop") == [] and system.calls("start") == []


def test_handover_lifecycle_does_not_overwrite_a_running_start_record(tmp_path):
    runtime_state.write_lifecycle(action="start", phase="running", pid=4242, directory=tmp_path)
    runtime_state.write_lifecycle(action="handover", phase="finished", result="READY", pid=1, directory=tmp_path)
    assert runtime_state.read_lifecycle(tmp_path)["action"] == "start"
    assert runtime_state.read_lifecycle(tmp_path)["phase"] == "running"
    assert runtime_state.read_handover_lifecycle(tmp_path)["action"] == "handover"
    runtime_state.write_lifecycle(action="start", phase="finished", result="READY", pid=4242, directory=tmp_path)
    runtime_state.write_lifecycle(action="handover", phase="running", pid=1, directory=tmp_path)
    assert runtime_state.read_lifecycle(tmp_path)["action"] == "handover"   # nothing to protect any more


def test_systemd_templates_mirror_the_live_unit_and_order_one_direction_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "systemd"
    primary = (root / "llama-server-primary.service").read_text(encoding="utf-8")
    expert = (root / "llama-server-expert.service").read_text(encoding="utf-8")
    assert "Conflicts=llama-server-expert.service" in primary and "Conflicts=llama-server-primary.service" in expert
    after = [l for l in primary.splitlines() if l.startswith("After=")][0]
    assert "llama-server-expert.service" in after                       # primary starts after the expert is gone
    assert not any("llama-server-primary" in l for l in expert.splitlines() if l.startswith(("After=", "Before=")))  # no cycle
    for needle in ("--ctx-size 8192", "--mmproj", "--reasoning-effort none", "HSA_ENABLE_DXG_DETECTION=1",
                   "ROCM_PATH=/opt/rocm", "--port 8080", "--host 127.0.0.1"):
        assert needle in primary, needle
    assert "--mmproj \\" not in expert and "--port 8082" in expert   # ExecStart flag, not the comment
    assert "LIVE unit lives in ~/.config/systemd/user" in primary and "NOT a VRAM guarantee" in primary
