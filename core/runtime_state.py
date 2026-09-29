"""Shared runtime state files for the JARVIS control plane.

Two small JSON files live in the per-user runtime directory that ``start.sh``
already uses for its lifecycle lock:

* ``voice-heartbeat.json`` — written by the voice daemon's watchdog thread.
  It is the only liveness evidence that comes from *inside* the daemon.
* ``lifecycle.json`` — written by ``start.sh``/``stop.sh``/``restart.sh`` (via
  ``scripts/runtime_status.py --record-lifecycle``). It records what the last
  controlled lifecycle action is doing or did.

The runtime supervisor (``scripts/runtime_status.py``) only *reads* these files
and combines them with live service probes. Nothing here decides a state.
Stdlib only, so it can be imported by the watchdog and by the WSL probe alike.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = 1
HEARTBEAT_FILE = "voice-heartbeat.json"
LIFECYCLE_FILE = "lifecycle.json"
HANDOVER_LIFECYCLE_FILE = "lifecycle-handover.json"  # handover records while a start/stop/restart record is running


def state_dir() -> Path:
    """Runtime directory shared with start.sh (``$STATE_DIR``)."""
    override = os.environ.get("JARVIS_RUNTIME_STATE_DIR")
    if override:
        return Path(override)
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "jarvis-runtime"


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("schema") == SCHEMA else None


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- heartbeat ---------------------------------------------------------------

def write_heartbeat(*, interval_seconds: float, pipeline_state: str,
                    listener_running: bool, directory: Path | None = None) -> None:
    _atomic_write((directory or state_dir()) / HEARTBEAT_FILE, {
        "schema": SCHEMA,
        "pid": os.getpid(),
        "invocationId": os.environ.get("INVOCATION_ID", ""),
        "updatedEpoch": time.time(),
        "updatedAt": iso_now(),
        "intervalSeconds": float(interval_seconds),
        "pipelineState": str(pipeline_state),
        "listenerRunning": bool(listener_running),
    })


def read_heartbeat(directory: Path | None = None) -> dict[str, Any] | None:
    return _read((directory or state_dir()) / HEARTBEAT_FILE)


# -- lifecycle record ----------------------------------------------------------

LIFECYCLE_ACTIONS = ("start", "stop", "restart", "handover")
LIFECYCLE_PHASES = ("running", "finished")
LIFECYCLE_RESULTS = ("READY", "DEGRADED", "STOPPED", "ERROR")


def write_lifecycle(*, action: str, phase: str, result: str = "", message: str = "",
                    pid: int, directory: Path | None = None) -> None:
    if action not in LIFECYCLE_ACTIONS or phase not in LIFECYCLE_PHASES:
        raise ValueError("unknown lifecycle action or phase")
    if result and result not in LIFECYCLE_RESULTS:
        raise ValueError("unknown lifecycle result")
    target = LIFECYCLE_FILE
    if action == "handover":
        # A handover must never overwrite a running start/stop/restart record (the supervisor's orphan
        # detection depends on it): it goes to a separate file while such a record is running.
        current = _read((directory or state_dir()) / LIFECYCLE_FILE)
        if current and current.get("action") != "handover" and current.get("phase") == "running":
            target = HANDOVER_LIFECYCLE_FILE
    _atomic_write((directory or state_dir()) / target, {
        "schema": SCHEMA,
        "action": action,
        "phase": phase,
        "result": result,
        "message": message[:300],
        "pid": int(pid),
        "updatedAt": iso_now(),
    })


def read_lifecycle(directory: Path | None = None) -> dict[str, Any] | None:
    return _read((directory or state_dir()) / LIFECYCLE_FILE)


def read_handover_lifecycle(directory: Path | None = None) -> dict[str, Any] | None:
    return _read((directory or state_dir()) / HANDOVER_LIFECYCLE_FILE)


# -- model handover (Primary <-> Expert GPU swap) -----------------------------------
#
# ``core/model_handover.py`` publishes its live state here so the runtime probe and the
# watchdog (separate processes) can treat a handover as a *controlled transition* instead
# of an outage. A handover also writes lifecycle records with action ``handover``; the
# probe ignores those for its start/stop orphan logic (no lifecycle script owns them).

HANDOVER_FILE = "handover.json"
# The handover refreshes its record every ``handover.heartbeat_s`` (15 s) during ALL phases. A record
# whose heartbeat is older than this (or whose pid is dead) is a leftover of a crash, not "swapping".
HANDOVER_MAX_AGE_S = 90.0


def _pid_alive(pid: Any) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return True  # record without a usable pid: judge by heartbeat age only
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # exists but not ours (EPERM)
    return True


def write_handover(state: dict[str, Any], directory: Path | None = None) -> None:
    payload = dict(state)
    payload.setdefault("pid", os.getpid())
    payload.update({"schema": SCHEMA, "updatedEpoch": time.time(), "updatedAt": iso_now()})
    _atomic_write((directory or state_dir()) / HANDOVER_FILE, payload)


def read_handover(directory: Path | None = None) -> dict[str, Any] | None:
    return _read((directory or state_dir()) / HANDOVER_FILE)


def handover_in_progress(directory: Path | None = None, *, max_age: float = HANDOVER_MAX_AGE_S) -> dict[str, Any] | None:
    """The live handover record while a swap/restore is running, else None.

    Live = ``is_swapping``, heartbeat younger than ``max_age`` and the owning pid still exists.
    A record of a crashed process is NOT a transition (see :func:`stale_handover`).
    """
    record = read_handover(directory)
    if not record or not record.get("is_swapping"):
        return None
    try:
        age = time.time() - float(record.get("updatedEpoch", 0))
    except (TypeError, ValueError):
        return None
    if not 0 <= age <= max_age or not _pid_alive(record.get("pid")):
        return None
    return record


def stale_handover(directory: Path | None = None, *, max_age: float = HANDOVER_MAX_AGE_S) -> dict[str, Any] | None:
    """A record still claiming ``is_swapping`` although its owner is gone (crash/kill), else None."""
    record = read_handover(directory)
    if not record or not record.get("is_swapping"):
        return None
    return None if handover_in_progress(directory, max_age=max_age) is not None else record


def primary_endpoint(config: Any, default: str = "http://127.0.0.1:8080/v1/chat/completions") -> str:
    """Primary LLM chat endpoint: ``llm.primary.endpoint``, else the legacy ``llm.local.endpoint``, else default.

    Single source for every caller that used to hardcode port 8080 (config may be None).
    """
    if config is None:
        return default
    return config.get("llm.primary.endpoint", None) or config.get("llm.local.endpoint", default) or default


def primary_base_url(config: Any) -> str:
    """``http://host:port`` of the primary (endpoint without the /v1/... path)."""
    return primary_endpoint(config).split("/v1/")[0].rstrip("/")


# -- generic component status (written by other processes, read by the probe) -------

def _component_file(name: str) -> str:
    safe = "".join(c for c in str(name) if c.isalnum() or c in "-_")
    if not safe:
        raise ValueError("invalid component name")
    return f"component-{safe}.json"


def write_component_status(name: str, status: dict[str, Any], directory: Path | None = None) -> None:
    """Export real telemetry of a component (e.g. ``npu-sensor`` from the presence detector).

    Only report what is measured. A component that never writes stays "unknown" for the probe.
    """
    payload = dict(status)
    payload.update({"schema": SCHEMA, "updatedEpoch": time.time(), "updatedAt": iso_now()})
    _atomic_write((directory or state_dir()) / _component_file(name), payload)


def read_component_status(name: str, directory: Path | None = None, *, max_age: float | None = None) -> dict[str, Any] | None:
    record = _read((directory or state_dir()) / _component_file(name))
    if record is None or max_age is None:
        return record
    try:
        return record if 0 <= time.time() - float(record.get("updatedEpoch", 0)) <= max_age else None
    except (TypeError, ValueError):
        return None


# -- NPU sensor: ONE shared schema for writer (presence detector) and reader (runtime probe) --
#
# component-npu-sensor.json (besides schema/updatedEpoch/updatedAt added by the writer):
#   state            "READY" | "DEGRADED" | "STOPPED"   sensor state as the detector sees it
#   reason           str | None                         why not READY (fallback / camera reason)
#   active           "npu" | "cpu" | None               face backend actually in use
#   enabled          bool                               presence detection switched on
#   wake_signal      "NOT_IMPLEMENTED"                  never claimed
#   live_camera_npu  "NOT_IMPLEMENTED"                  never claimed
# The detector republishes every NPU_SENSOR_REPUBLISH_S even when unchanged; the probe treats a
# record older than NPU_SENSOR_MAX_AGE_S as unknown (NOT_IMPLEMENTED), never as a live state.

NPU_SENSOR = "npu-sensor"
NPU_SENSOR_REPUBLISH_S = 60.0
NPU_SENSOR_MAX_AGE_S = 300.0


def npu_sensor_record(*, state: str, reason: str | None, active: str | None, enabled: bool = True,
                      wake_signal: str = "NOT_IMPLEMENTED", live_camera_npu: str = "NOT_IMPLEMENTED") -> dict[str, Any]:
    return {"state": str(state), "reason": None if reason is None else str(reason),
            "active": active if active in ("npu", "cpu") else None, "enabled": bool(enabled),
            "wake_signal": wake_signal, "live_camera_npu": live_camera_npu}


def write_npu_sensor(record: dict[str, Any], directory: Path | None = None) -> None:
    write_component_status(NPU_SENSOR, npu_sensor_record(
        state=record.get("state", "STOPPED"), reason=record.get("reason"), active=record.get("active"),
        enabled=record.get("enabled", True), wake_signal=record.get("wake_signal", "NOT_IMPLEMENTED"),
        live_camera_npu=record.get("live_camera_npu", "NOT_IMPLEMENTED")), directory)


def main(argv: list[str] | None = None) -> int:
    """Write path for start.sh/stop.sh/restart.sh (stdlib only, run by file path).

    Usage: runtime_state.py ACTION PHASE [--result R] [--message M] [--pid N]
           runtime_state.py --handover-live   (exit 0 while a live handover runs)
    """
    import argparse
    import sys

    args_in = sys.argv[1:] if argv is None else argv
    if args_in[:1] == ["--handover-live"]:
        # Guard for stop.sh/restart.sh: exit 0 + "STATE PID" while a live model handover runs, else exit 1.
        live = handover_in_progress()
        if live is None:
            return 1
        print(f"{live.get('state', '?')} {live.get('pid', '?')}")
        return 0

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("action")
    parser.add_argument("phase")
    parser.add_argument("--result", default="")
    parser.add_argument("--message", default="")
    parser.add_argument("--pid", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        write_lifecycle(action=args.action, phase=args.phase, result=args.result,
                        message=args.message, pid=args.pid or os.getppid())
    except (OSError, ValueError) as exc:
        print(f"Lifecycle-Record nicht geschrieben ({type(exc).__name__}).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
