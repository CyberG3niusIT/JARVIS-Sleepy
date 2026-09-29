"""Primary <-> Expert model handover (one large model on the GPU at a time).

Flow of :meth:`ModelHandover.run_expert` (plan "Schritt 4"):

    save conversation state -> stop primary (systemctl --user) -> verify unit/port gone
    -> wait for VRAM release -> start expert -> wait for expert /health
    -> call_expert(task) -> store result -> stop expert -> verify gone
    -> START PRIMARY IN THE BACKGROUND -> restore conversation state

The expert answer is returned to the caller BEFORE the primary is READY again, so it can go
straight to TTS. Requests arriving while the primary reloads are queued honestly
(:meth:`wait_primary_ready`, :meth:`resolve_provider`); a fallback provider is only used
when it is really configured and reachable, never faked.

Hard rules: user-scope ``systemctl --user`` only (this is NOT ``core/gpu_swap.py``); never
both model units active; the expert is never started if the primary stop could not be
verified; the primary is restored in a ``finally`` path even after expert failures; a
failure is reported honestly (DEGRADED/ERROR with reason), never as READY.

All side effects are injectable (``systemctl``, ``health``, ``port_listening``, ``clock``,
``sleep``) so the whole cycle is testable with fakes. Nothing here starts on import.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from urllib.parse import urlsplit

logger = logging.getLogger("jarvis.model_handover")

DEFAULT_PRIMARY_UNIT = "llama-server-primary.service"
DEFAULT_EXPERT_UNIT = "llama-server-expert.service"
DEFAULT_PRIMARY_ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_EXPERT_ENDPOINT = "http://127.0.0.1:8082/v1/chat/completions"


class HandoverState(str, Enum):
    IDLE = "IDLE"
    SAVING_STATE = "SAVING_STATE"
    STOPPING_PRIMARY = "STOPPING_PRIMARY"
    WAITING_VRAM_RELEASE = "WAITING_VRAM_RELEASE"
    STARTING_EXPERT = "STARTING_EXPERT"
    EXPERT_RUNNING = "EXPERT_RUNNING"
    STOPPING_EXPERT = "STOPPING_EXPERT"
    RESTORING_PRIMARY = "RESTORING_PRIMARY"


class HandoverError(RuntimeError):
    """A handover phase failed; ``code`` is a stable machine-readable reason."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass
class ExpertRunResult:
    ok: bool
    answer: Any = None
    error: str = ""
    timings: dict = field(default_factory=dict)
    primary_restore_started: bool = False


@dataclass
class ProviderDecision:
    provider: str          # "primary" | "fallback" | "unavailable"
    status: str            # lifecycle status of the primary at decision time
    waited_s: float = 0.0
    reason: str = ""


# -- default (real) side-effect implementations ---------------------------------------

def _default_systemctl(*args: str) -> tuple:
    try:
        result = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True,
                                timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, type(exc).__name__
    return result.returncode, (result.stdout or "").strip()


def _endpoint_port(endpoint: str) -> int | None:
    try:
        return urlsplit(endpoint).port
    except ValueError:
        return None


def _http_health(endpoint: str, timeout: float = 2.0) -> bool:
    parts = urlsplit(endpoint)
    if parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost", "::1"):
        return False  # loopback HTTP only, same rule as check_runtime_dependencies
    url = f"{parts.scheme}://{parts.netloc}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (loopback only)
            payload = json.loads(response.read().decode("utf-8", "replace") or "{}")
            return response.status == 200 and payload.get("status", "ok") == "ok"
    except Exception:
        return False


def _tcp_listening(port: int | None, timeout: float = 0.5) -> bool:
    if not port:
        return False
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except OSError:
        return False


class ModelHandover:
    """Controls the exclusive Primary/Expert model swap. One instance per process."""

    def __init__(
        self,
        config: Any = None,
        *,
        systemctl: Callable[..., tuple] | None = None,
        health: Callable[[str], bool] | None = None,
        port_listening: Callable[[str], bool] | None = None,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
        fallback_available: Callable[[], bool] | None = None,
        publish: bool = True,
        state_dir: Any = None,
        reconcile: bool = False,
    ):
        def get(key: str, default: Any = None) -> Any:
            return config.get(key, default) if config is not None else default

        self._units = {
            "primary": get("handover.units.primary") or DEFAULT_PRIMARY_UNIT,
            "expert": get("handover.units.expert") or DEFAULT_EXPERT_UNIT,
        }
        self._endpoints = {
            "primary": get("llm.primary.endpoint") or get("llm.local.endpoint") or DEFAULT_PRIMARY_ENDPOINT,
            "expert": get("llm.expert.endpoint") or DEFAULT_EXPERT_ENDPOINT,
        }
        self._stop_timeout = float(get("handover.stop_timeout_s", 60))
        self._primary_start_timeout = float(get("handover.primary_start_timeout_s", 300))
        self._expert_start_timeout = float(get("handover.expert_start_timeout_s", 300))
        self._vram_wait = float(get("handover.vram_release_wait_s", 3))
        self._poll = float(get("handover.poll_interval_s", 1))
        self._queue_wait = float(get("handover.queue_wait_s", 120))
        self._health_ttl = float(get("llm.primary.health_ttl_s", 2.0) or 0.0)
        self._heartbeat_s = float(get("handover.heartbeat_s", 15) or 0.0)

        self._systemctl = systemctl or _default_systemctl
        self._health = health or (lambda role: _http_health(self._endpoints[role]))
        self._port_listening = port_listening or (lambda role: _tcp_listening(_endpoint_port(self._endpoints[role])))
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._fallback_available = fallback_available
        self._publish = publish
        self._state_dir = state_dir

        self._cond = threading.Condition()
        self._run_lock = threading.Lock()
        self._state = HandoverState.IDLE
        self._primary_ready: bool | None = None
        self._expert_ready = False
        self._error = ""
        self._fatal = False
        self._timings: dict = {}
        self._last_answer: Any = None
        self._restore_thread: threading.Thread | None = None
        self._primary_probe_at: float | None = None
        self._hb_stop: threading.Event | None = None
        if reconcile:
            # Crash recovery at daemon start; explicit and opt-in so fake-driven tests stay deterministic.
            try:
                self.reconcile()
            except Exception:
                logger.warning("handover reconcile failed", exc_info=True)

    # -- status ---------------------------------------------------------------------

    @property
    def state(self) -> HandoverState:
        return self._state

    @property
    def is_swapping(self) -> bool:
        return self._state is not HandoverState.IDLE

    @property
    def last_answer(self) -> Any:
        return self._last_answer

    def _set_primary_ready(self, value: bool) -> None:
        self._primary_ready = value
        self._primary_probe_at = self._clock()

    @property
    def primary_ready(self) -> bool:
        """Cached primary health. While idle it is re-probed after ``llm.primary.health_ttl_s``, so a
        stale False never sticks ("Sprachmodell wird geladen" forever) and a good probe clears the error."""
        if not self.is_swapping:
            now = self._clock()
            stale = (self._primary_ready is None or self._primary_probe_at is None
                     or now - self._primary_probe_at >= self._health_ttl)
            if stale:
                healthy = self._safe_health("primary")
                self._set_primary_ready(healthy)
                if healthy:
                    self._error = ""
                    self._fatal = False
        return bool(self._primary_ready)

    def lifecycle_state(self) -> str:
        """Maps the handover onto the runtime lifecycle vocabulary."""
        if self._state is not HandoverState.IDLE:
            return "STARTING"
        if self._fatal:
            return "ERROR"
        if self.primary_ready:
            return "READY"
        return "DEGRADED" if self._error else "STOPPED"

    def status(self) -> dict:
        return {
            "state": self._state.value,
            "lifecycle": self.lifecycle_state(),
            "is_swapping": self.is_swapping,
            "restoring_primary": self._state is HandoverState.RESTORING_PRIMARY,
            "primary_ready": bool(self._primary_ready),
            "expert_ready": self._expert_ready,
            "timings": dict(self._timings),
            "error": self._error,
            "units": dict(self._units),
        }

    # -- waiting / provider choice ----------------------------------------------------

    def wait_primary_ready(self, timeout: float | None = None) -> bool:
        """Block until no handover is running and the primary is READY (queue behaviour)."""
        timeout = self._queue_wait if timeout is None else timeout
        deadline = time.monotonic() + max(0.0, timeout)
        with self._cond:
            while self.is_swapping:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(remaining)
        return self.primary_ready

    def resolve_provider(self, timeout: float | None = None) -> ProviderDecision:
        """Where may a request go right now? Honest: primary, a REAL fallback, or unavailable."""
        started = time.monotonic()
        if not self.is_swapping and self.primary_ready:
            return ProviderDecision("primary", "READY")
        if self.wait_primary_ready(timeout):
            return ProviderDecision("primary", "READY", time.monotonic() - started)
        waited = time.monotonic() - started
        status = self.lifecycle_state()
        if self._fallback_available is not None:
            try:
                if self._fallback_available():
                    return ProviderDecision("fallback", status, waited, "primary_not_ready_fallback_configured")
            except Exception:
                logger.warning("fallback availability check failed", exc_info=True)
        return ProviderDecision("unavailable", status, waited, "primary_not_ready_no_fallback")

    # -- the handover -----------------------------------------------------------------

    def run_expert(
        self,
        task: Any,
        call_expert: Callable[[Any], Any],
        save_state: Callable[[], Any] | None = None,
        restore_state: Callable[[Any], None] | None = None,
    ) -> ExpertRunResult:
        """Run one task on the expert and put the primary back. Returns before primary is READY."""
        if not self._run_lock.acquire(blocking=False):
            return ExpertRunResult(False, error="handover_busy")
        if self._state is not HandoverState.IDLE:  # background restore still running
            self._run_lock.release()
            return ExpertRunResult(False, error="handover_busy")

        result = ExpertRunResult(False)
        snapshot: Any = None
        primary_stop_issued = False
        expert_start_issued = False
        try:
            self._timings = {}
            self._error = ""
            self._fatal = False
            self._record("running", "", "Expert-Handover gestartet.")
            try:
                self._set(HandoverState.SAVING_STATE)
                t = self._clock()
                snapshot = save_state() if save_state else None
                self._timings["save_state"] = self._clock() - t
            except Exception as exc:
                raise HandoverError("save_state_failed", type(exc).__name__)

            self._set(HandoverState.STOPPING_PRIMARY)
            t = self._clock()
            primary_stop_issued = True
            self._systemctl("stop", self._units["primary"])
            self._wait_gone("primary", "primary_stop_not_verified")
            self._set_primary_ready(False)
            self._timings["stop_primary"] = self._clock() - t

            self._set(HandoverState.WAITING_VRAM_RELEASE)
            t = self._clock()
            self._sleep(self._vram_wait)
            self._timings["vram_release_wait"] = self._clock() - t

            # Mutex: re-verify right before the expert starts.
            if self._is_active("primary") or self._port_listening("primary"):
                raise HandoverError("primary_stop_not_verified", "primary still present before expert start")

            self._set(HandoverState.STARTING_EXPERT)
            t = self._clock()
            expert_start_issued = True
            rc, _ = self._systemctl("start", self._units["expert"])
            if rc != 0:
                raise HandoverError("expert_start_failed", f"rc={rc}")
            self._wait_health("expert", self._expert_start_timeout, "expert_health_timeout")
            self._expert_ready = True
            self._timings["start_expert"] = self._clock() - t

            self._set(HandoverState.EXPERT_RUNNING)
            t = self._clock()
            result.answer = call_expert(task)
            self._timings["expert_call"] = self._clock() - t
            self._last_answer = result.answer
            result.ok = True
        except HandoverError as exc:
            result.error = exc.code
            self._error = str(exc)
            logger.warning("Expert handover failed: %s", exc)
        except Exception as exc:
            result.error = f"expert_call_failed:{type(exc).__name__}"
            self._error = result.error
            logger.warning("Expert call failed: %s", type(exc).__name__)
        finally:
            try:
                self._finalize(result, snapshot, restore_state, primary_stop_issued, expert_start_issued)
            finally:
                self._run_lock.release()
        return result

    def _finalize(self, result: ExpertRunResult, snapshot: Any,
                  restore_state: Callable[[Any], None] | None,
                  primary_stop_issued: bool, expert_start_issued: bool) -> None:
        expert_gone = True
        if expert_start_issued:
            self._set(HandoverState.STOPPING_EXPERT)
            t = self._clock()
            self._systemctl("stop", self._units["expert"])
            self._expert_ready = False
            try:
                self._wait_gone("expert", "expert_stop_not_verified")
            except HandoverError as exc:
                expert_gone = False
                result.ok = False
                result.error = exc.code
                self._error = str(exc)
            self._timings["stop_expert"] = self._clock() - t
        result.timings = self._timings

        needs_restore = primary_stop_issued and not self._is_active("primary")
        if needs_restore and not expert_gone:
            # Mutex: never start the primary while an expert may still hold the GPU.
            self._fatal = True
            self._set_primary_ready(False)
            self._finish_idle("ERROR", "Expert nicht sicher gestoppt; Primary bleibt aus.")
        elif needs_restore:
            result.primary_restore_started = True
            self._set(HandoverState.RESTORING_PRIMARY)
            thread = threading.Thread(target=self._restore_primary, args=(snapshot, restore_state),
                                      name="handover-restore-primary", daemon=True)
            self._restore_thread = thread
            thread.start()
        else:
            # The primary was never taken down (early failure or stop not effective): nothing to reload.
            self._set_primary_ready(self._safe_health("primary"))
            self._finish_idle("READY" if self._primary_ready else "DEGRADED", self._error)

    # -- crash recovery ---------------------------------------------------------------

    def reconcile(self) -> str:
        """Bring the two units back to a consistent state after a crash/kill mid-handover.

        * expert active and NO live handover record (owner pid dead / heartbeat stale / no record):
          stop the expert (verified), then make sure the primary is running (background restore).
        * expert not active but a stale ``is_swapping`` record and the primary is down: restore the
          primary the same way.
        * a live handover of another process, or a healthy resting state: nothing to do.

        Returns "none", "busy", "live_handover", "restore_primary" or "expert_stop_failed".
        Never called implicitly except via ``ModelHandover(..., reconcile=True)``.
        """
        from core import runtime_state
        if not self._run_lock.acquire(blocking=False):
            return "busy"
        try:
            if self._state is not HandoverState.IDLE:
                return "busy"
            live = runtime_state.handover_in_progress(self._state_dir)
            if live is not None and live.get("pid") != os.getpid():
                return "live_handover"
            stale = runtime_state.stale_handover(self._state_dir) is not None
            expert_present = self._is_active("expert") or self._port_listening("expert")
            primary_present = self._is_active("primary")
            if not expert_present and not (stale and not primary_present):
                if stale:
                    self._publish_state()  # clear the leftover is_swapping claim
                return "none"
            logger.warning("Handover reconcile: expert_present=%s primary_present=%s stale_record=%s",
                           expert_present, primary_present, stale)
            self._error = ""
            self._fatal = False
            if expert_present:
                self._set(HandoverState.STOPPING_EXPERT)
                self._systemctl("stop", self._units["expert"])
                self._expert_ready = False
                try:
                    self._wait_gone("expert", "expert_stop_not_verified")
                except HandoverError as exc:
                    self._error = str(exc)
                    self._fatal = True
                    self._set_primary_ready(False)
                    self._finish_idle("ERROR", "Reconcile: Expert nicht sicher gestoppt; Primary bleibt aus.")
                    return "expert_stop_failed"
            if self._is_active("primary"):
                self._set_primary_ready(self._safe_health("primary"))
                self._finish_idle("READY" if self._primary_ready else "DEGRADED", "Reconcile: Expert gestoppt.")
                return "none"
            self._set_primary_ready(False)
            self._set(HandoverState.RESTORING_PRIMARY)
            thread = threading.Thread(target=self._restore_primary, args=(None, None),
                                      name="handover-reconcile-primary", daemon=True)
            self._restore_thread = thread
            thread.start()
            return "restore_primary"
        finally:
            self._run_lock.release()

    # -- background restore -----------------------------------------------------------

    def join_restore(self, timeout: float | None = None) -> bool:
        """Wait for the background primary restore (tests / orderly shutdown)."""
        thread = self._restore_thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def _restore_primary(self, snapshot: Any, restore_state: Callable[[Any], None] | None) -> None:
        t = self._clock()
        outcome, message = "READY", "Primary wiederhergestellt."
        try:
            if self._is_active("expert") or self._port_listening("expert"):
                raise HandoverError("expert_still_present", "mutex: refusing to start primary")
            rc, _ = self._systemctl("start", self._units["primary"])
            if rc != 0:
                raise HandoverError("primary_start_failed", f"rc={rc}")
            self._wait_health("primary", self._primary_start_timeout, "primary_health_timeout")
            self._set_primary_ready(True)
        except HandoverError as exc:
            self._set_primary_ready(False)
            self._error = str(exc)
            self._fatal = exc.code != "primary_health_timeout"
            outcome = "ERROR" if self._fatal else "DEGRADED"
            message = f"Primary nicht wiederhergestellt: {exc.code}"
            logger.error("Primary restore failed: %s", exc)
        except Exception as exc:  # defensive: the state must never stay in RESTORING
            self._set_primary_ready(False)
            self._error = f"primary_restore_failed:{type(exc).__name__}"
            self._fatal = True
            outcome, message = "ERROR", self._error
        self._timings["restore_primary"] = self._clock() - t
        try:
            if restore_state is not None:
                restore_state(snapshot)
        except Exception:
            logger.warning("Conversation state restore failed", exc_info=True)
            self._error = self._error or "restore_state_failed"
        self._finish_idle(outcome, message)

    # -- helpers ----------------------------------------------------------------------

    def _is_active(self, role: str) -> bool:
        _, out = self._systemctl("is-active", self._units[role])
        return out.strip() in ("active", "activating", "deactivating", "reloading")

    def _safe_health(self, role: str) -> bool:
        try:
            return bool(self._health(role))
        except Exception:
            return False

    def _wait_gone(self, role: str, code: str) -> None:
        deadline = self._clock() + self._stop_timeout
        while True:
            if not self._is_active(role) and not self._port_listening(role):
                return
            if self._clock() >= deadline:
                raise HandoverError(code, f"{self._units[role]} noch aktiv oder Port belegt")
            self._sleep(self._poll)

    def _unit_dead(self, role: str) -> bool:
        """True when systemd says the unit failed or is inactive (fail fast instead of waiting out the timeout)."""
        try:
            _, out = self._systemctl("is-active", self._units[role])
        except Exception:
            return False
        return out.strip() in ("failed", "inactive")

    def _wait_health(self, role: str, timeout: float, code: str) -> None:
        deadline = self._clock() + timeout
        while True:
            if self._safe_health(role):
                return
            if self._unit_dead(role):
                raise HandoverError(f"{role}_unit_failed", f"{self._units[role]} ist fehlgeschlagen oder nicht aktiv")
            if self._clock() >= deadline:
                raise HandoverError(code, f"{role} /health nicht bereit")
            self._sleep(self._poll)

    def _set(self, state: HandoverState) -> None:
        with self._cond:
            self._state = state
            self._cond.notify_all()
        self._publish_state()
        self._start_heartbeat()

    def _start_heartbeat(self) -> None:
        """Refresh handover.json while a swap runs, so readers can tell a live swap from a dead one."""
        if not self._publish or self._heartbeat_s <= 0 or self._hb_stop is not None:
            return
        stop = threading.Event()
        self._hb_stop = stop

        def beat() -> None:
            while not stop.wait(self._heartbeat_s):
                if self._state is HandoverState.IDLE:
                    break
                self._publish_state()

        threading.Thread(target=beat, name="handover-heartbeat", daemon=True).start()

    def _stop_heartbeat(self) -> None:
        stop, self._hb_stop = self._hb_stop, None
        if stop is not None:
            stop.set()

    def _finish_idle(self, result: str, message: str = "") -> None:
        with self._cond:
            self._state = HandoverState.IDLE
            self._cond.notify_all()
        self._stop_heartbeat()
        self._publish_state()
        timings = " ".join(f"{k}={v:.1f}s" for k, v in self._timings.items())
        self._record("finished", result, f"{message} {timings}".strip())

    def _publish_state(self) -> None:
        if not self._publish:
            return
        try:
            from core import runtime_state
            runtime_state.write_handover(self.status(), self._state_dir)
        except Exception:
            logger.debug("handover state not published", exc_info=True)

    def _record(self, phase: str, result: str, message: str) -> None:
        if not self._publish:
            return
        try:
            from core import runtime_state
            runtime_state.write_lifecycle(action="handover", phase=phase, result=result,
                                          message=message, pid=os.getpid(), directory=self._state_dir)
        except Exception:
            logger.debug("handover lifecycle record not written", exc_info=True)
