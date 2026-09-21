"""
JARVIS Internal Watchdog — proactive self-healing for the voice pipeline.

Runs as a daemon thread inside the JARVIS process.  Every `check_interval`
seconds it runs lightweight health checks against the coordinator, listener,
queues, and llama-server, and takes graduated recovery actions:

    1. Silent self-fix  (clear stuck flags, drain queues)
    2. Logged warning   (for post-mortem analysis)
    3. Spoken announcement (last resort, rate-limited)

Usage:
    from core.watchdog import Watchdog

    wd = Watchdog(config=config, coordinator=coordinator,
                  listener=listener, tts=tts,
                  event_queue=eq, audio_queue=aq, tts_queue=tq)
    wd.start()   # daemon thread — dies with the process
"""

import queue
import subprocess
import threading
import time

import requests

from core.events import Event, EventType, PipelineState
from core.logger import get_logger


class Watchdog(threading.Thread):
    """Background self-healing monitor for the JARVIS voice pipeline."""

    def __init__(self, *, config, coordinator, listener, tts,
                 event_queue, audio_queue, tts_queue,
                 task_planner=None, reminder_manager=None,
                 weather_poller=None, news_manager=None):
        super().__init__(daemon=True, name="watchdog")
        self.logger = get_logger("core.watchdog", config)

        self._coordinator = coordinator
        self._listener = listener
        self._tts = tts
        self._event_queue = event_queue
        self._audio_queue = audio_queue
        self._tts_queue = tts_queue

        # Session #8 (agentic-audit open finding): the watchdog previously
        # had zero visibility into anything outside the voice pipeline
        # itself — a dead reminder/weather/news poll thread, or a
        # TaskPlanner plan stuck mid-step, would never be noticed. These
        # are all optional (default None) so existing call sites that
        # don't pass them keep working exactly as before — a caller
        # simply gets no visibility into whichever ones it omits, not an
        # error.
        self._task_planner = task_planner
        self._background_managers = {
            name: mgr for name, mgr in {
                "reminder_manager": reminder_manager,
                "weather_poller": weather_poller,
                "news_manager": news_manager,
            }.items() if mgr is not None
        }

        # Configuration
        self._check_interval = config.get("watchdog.check_interval", 10)
        self._listener_stuck_threshold = config.get("watchdog.listener_stuck_threshold", 60)
        self._command_hung_threshold = config.get("watchdog.command_hung_threshold", 120)
        self._queue_backlog_threshold = config.get("watchdog.queue_backlog_threshold", 10)
        self._llm_health_interval = config.get("watchdog.llm_health_interval", 30)
        self._recovery_cooldown = config.get("watchdog.recovery_cooldown", 300)
        self._announce_failures = config.get("watchdog.announce_failures", True)
        self._max_announcements_per_hour = config.get("watchdog.max_announcements_per_hour", 3)
        # A poll thread that hasn't started a new iteration within this
        # many multiples of its OWN poll_interval is considered stuck —
        # generous, so a slow-but-fine iteration (e.g. a slow RSS feed)
        # never false-positives.
        self._poll_stuck_multiplier = config.get("watchdog.poll_stuck_multiplier", 3)

        # Internal state
        self._recovery_log: dict[str, float] = {}        # check_name → last recovery time
        self._announcement_times: list[float] = []        # monotonic timestamps
        self._last_llm_check_ts: float = 0.0
        self._llm_status: str | None = None               # None = healthy
        self._llm_unhealthy_count: int = 0
        self._flux_detected_ts: float = 0.0
        self._flux_grace_period: int = 400  # seconds — covers 300s generation + 90s startup + buffer
        self._stop_event = threading.Event()

        # Background-worker visibility state (session #8)
        self._worker_status: dict[str, str] = {}   # name -> "healthy"|"dead"|"stuck"|"unknown"
        self._plan_step_seen: tuple | None = None   # ((plan_id, step_id), first_seen_monotonic)
        self._plan_stuck_logged: bool = False

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        self.logger.info(
            "Watchdog started (interval=%ds, listener_stuck=%ds, command_hung=%ds)",
            self._check_interval, self._listener_stuck_threshold,
            self._command_hung_threshold,
        )
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._check_interval)
            if self._stop_event.is_set():
                break
            if not self._coordinator.running:
                break
            try:
                self._run_checks()
            except Exception as e:
                self.logger.error("Watchdog check cycle error: %s", e, exc_info=True)
        self.logger.info("Watchdog stopped")

    def stop(self):
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Check dispatch
    # ------------------------------------------------------------------

    def _run_checks(self):
        # Order matters: clear cheap false-positive sources first
        if self._check_streaming_orphan():
            self._recover_streaming_orphan()

        if self._check_speaking_stuck():
            self._recover_speaking_stuck()

        if self._check_listener_stuck():
            self._recover_listener_stuck()

        if self._check_command_hung():
            self._recover_command_hung()

        if self._check_stt_backlog():
            self._recover_stt_backlog()

        self._check_llm_health()
        self._check_background_workers()

    # ------------------------------------------------------------------
    # Check 1: Streaming orphan — _streaming_active=True but IDLE
    # ------------------------------------------------------------------

    def _check_streaming_orphan(self) -> bool:
        if not self._coordinator._streaming_active:
            return False
        return self._coordinator.state == PipelineState.IDLE

    def _recover_streaming_orphan(self):
        self._coordinator._streaming_active = False
        self.logger.warning("Cleared orphaned _streaming_active flag")
        self._emit_recovery("streaming_orphan", "Cleared orphaned _streaming_active flag")

    # ------------------------------------------------------------------
    # Check 2: Speaking flags stuck — listener paused but TTS idle
    # ------------------------------------------------------------------

    def _check_speaking_stuck(self) -> bool:
        listener = self._listener
        if not (listener.speaking or listener._speaking_event.is_set()):
            return False
        # LLM streaming in progress? (uses its own aplay, not tracked in TTS procs)
        if self._coordinator._streaming_active:
            return False  # legitimately streaming
        # TTS actively playing?
        with self._tts._active_procs_lock:
            tts_active = bool(self._tts._active_procs)
        if tts_active or self._tts_queue.qsize() > 0:
            return False  # legitimately speaking
        return True

    def _recover_speaking_stuck(self):
        if not self._can_recover("speaking_stuck"):
            return
        self._listener.speaking = False
        self._listener._speaking_event.clear()
        self._listener.resume_listening()
        self._record_recovery("speaking_stuck")
        self.logger.warning("Cleared stuck speaking flags, resumed listening")
        self._emit_recovery("speaking_stuck", "Cleared stuck speaking flags, resumed listening")

    # ------------------------------------------------------------------
    # Check 3: Listener stuck — no transcription while IDLE for too long
    # ------------------------------------------------------------------

    def _check_listener_stuck(self) -> bool:
        if not self._listener.running:
            return False
        if self._coordinator.state != PipelineState.IDLE:
            return False
        if self._listener.speaking or self._listener._speaking_event.is_set():
            return False
        # Only consider "stuck" if VAD has detected speech activity since the
        # last transcription — otherwise it's just silence (nobody talking),
        # which is normal and doesn't need recovery.
        last_vad = getattr(self._listener, '_last_vad_activity_ts', 0.0)
        last_tx = self._coordinator._last_transcription_ts
        if last_vad <= last_tx:
            return False  # No VAD activity since last transcription — just silence
        # Don't fire if listening recently resumed after TTS playback.
        # The last_tx timestamp may be stale from before a long TTS sequence
        # (greeting → briefing → rundown). Measure from the later of
        # last_tx or last_idle to avoid false "stuck" triggers.
        last_idle = self._coordinator._last_idle_ts
        baseline = max(last_tx, last_idle)
        idle_duration = time.monotonic() - baseline
        return idle_duration > self._listener_stuck_threshold

    def _recover_listener_stuck(self):
        if not self._can_recover("listener_stuck"):
            return
        self.logger.warning(
            "Listener appears stuck (no transcription for %.0fs) — attempting soft reset",
            time.monotonic() - self._coordinator._last_transcription_ts,
        )
        # Soft reset: clear any stuck state flags
        self._listener.speaking = False
        self._listener._speaking_event.clear()
        self._listener.collecting_speech = False
        self._listener.speech_buffer = []
        self._coordinator._streaming_active = False
        self._coordinator.state = PipelineState.IDLE
        self._listener.resume_listening()
        # Reset the timestamp so we don't immediately re-trigger
        self._coordinator._last_transcription_ts = time.monotonic()
        self._record_recovery("listener_stuck")
        self.logger.info("Listener soft reset complete")
        self._emit_recovery("listener_stuck", "Listener soft reset — no transcription for too long", metadata={
            "idle_duration_s": round(time.monotonic() - self._coordinator._last_transcription_ts, 1),
        })

    # ------------------------------------------------------------------
    # Check 4: Command processing hung
    # ------------------------------------------------------------------

    def _check_command_hung(self) -> bool:
        if self._coordinator.state == PipelineState.IDLE:
            return False
        if self._coordinator._last_command_start_ts == 0.0:
            return False
        elapsed = time.monotonic() - self._coordinator._last_command_start_ts
        return elapsed > self._command_hung_threshold

    def _recover_command_hung(self):
        if not self._can_recover("command_hung"):
            return
        elapsed = time.monotonic() - self._coordinator._last_command_start_ts
        self.logger.warning(
            "Command processing hung for %.0fs — forcing IDLE", elapsed
        )
        self._coordinator._streaming_active = False
        self._coordinator._llm_responded = True
        self._coordinator.state = PipelineState.IDLE
        self._coordinator._last_idle_ts = time.monotonic()
        self._listener.speaking = False
        self._listener._speaking_event.clear()
        self._listener.resume_listening()
        self._record_recovery("command_hung")
        self._emit_recovery("command_hung", f"Command processing hung for {elapsed:.0f}s — forced IDLE", metadata={
            "elapsed_s": round(elapsed, 1),
        })
        self._announce(
            "I'm sorry, I got stuck processing your last request. I'm back and listening."
        )

    # ------------------------------------------------------------------
    # Check 5: STT audio queue backlog
    # ------------------------------------------------------------------

    def _check_stt_backlog(self) -> bool:
        return self._audio_queue.qsize() > self._queue_backlog_threshold

    def _recover_stt_backlog(self):
        if not self._can_recover("stt_backlog"):
            return
        drained = 0
        while self._audio_queue.qsize() > 1:
            try:
                self._audio_queue.get_nowait()
                drained += 1
            except queue.Empty:
                break
        self._record_recovery("stt_backlog")
        self.logger.warning("Drained %d stale audio frames from queue", drained)
        self._emit_recovery("stt_backlog", f"Drained {drained} stale audio frames", metadata={
            "frames_drained": drained,
        })

    # ------------------------------------------------------------------
    # Check 6: llama-server health (periodic, not every cycle)
    # ------------------------------------------------------------------

    def _check_llm_health(self):
        now = time.monotonic()
        if now - self._last_llm_check_ts < self._llm_health_interval:
            return
        self._last_llm_check_ts = now

        # Respect GPU swap — expected downtime
        try:
            from core.gpu_swap import get_gpu_swap_manager
            swap = get_gpu_swap_manager()
            if swap and swap.is_swapping:
                if self._llm_status != "swapping":
                    self.logger.info("LLM offline — GPU swap in progress")
                self._llm_status = "swapping"
                self._llm_unhealthy_count = 0
                return
            if swap and not swap.is_llm_available:
                if self._llm_status != "gpu_swapped":
                    self.logger.info("LLM offline — GPU allocated to another service")
                self._llm_status = "gpu_swapped"
                self._llm_unhealthy_count = 0
                return
        except Exception:
            pass  # gpu_swap not initialized or import error

        # Cross-process check: flux-server may be running from web service GPU swap
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "flux-server.service"],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip() == "active":
                if self._llm_status != "flux_generating":
                    self._flux_detected_ts = time.monotonic()
                    self.logger.info("LLM offline — flux-server active (image generation in progress)")
                elif time.monotonic() - self._flux_detected_ts > self._flux_grace_period:
                    self.logger.warning(
                        "flux-server still running after %ds grace period — possible stuck generation",
                        self._flux_grace_period,
                    )
                    # Fall through to normal health check / announcement
                else:
                    # Within grace period — suppress
                    pass
                if time.monotonic() - self._flux_detected_ts <= self._flux_grace_period:
                    self._llm_status = "flux_generating"
                    self._llm_unhealthy_count = 0
                    return
        except Exception:
            pass

        try:
            r = requests.get("http://127.0.0.1:8080/health", timeout=3)
            if r.status_code == 200:
                data = r.json() if "json" in r.headers.get("content-type", "") else {}
                status = data.get("status", "ok")
                if status == "ok":
                    if self._llm_status and self._llm_status not in ("swapping", "gpu_swapped"):
                        self.logger.info("LLM back online (was: %s)", self._llm_status)
                    self._llm_status = None
                    self._llm_unhealthy_count = 0
                    return
                new_status = status  # e.g. "loading model"
            else:
                new_status = f"http_{r.status_code}"
        except (requests.ConnectionError, requests.Timeout):
            new_status = "unreachable"
        except Exception as e:
            new_status = f"error: {e}"

        # Track consecutive unhealthy checks
        if new_status != self._llm_status:
            self.logger.warning("LLM status changed: %s → %s", self._llm_status, new_status)
            self._emit_event(
                "error_recovery", "llm_status_changed",
                f"LLM status: {self._llm_status} → {new_status}",
                severity="warn",
                metadata={"old_status": self._llm_status, "new_status": new_status},
            )
        self._llm_status = new_status
        self._llm_unhealthy_count += 1

        # Announce after 2 consecutive unhealthy checks (not transient)
        if self._llm_unhealthy_count == 2 and new_status == "unreachable":
            self._announce(
                "System notification, sir. My language model is currently off line. "
                "I can still handle skill-based commands."
            )

    @property
    def llm_status(self) -> str | None:
        """Current LLM status. None = healthy."""
        return self._llm_status

    # ------------------------------------------------------------------
    # Check 7: background worker visibility (session #8 agentic-audit
    # open finding — the watchdog previously had zero visibility into
    # anything outside the voice pipeline: a reminder/weather/news poll
    # thread crashing silently, or a TaskPlanner step running forever,
    # went completely unnoticed. Detection only — no auto-restart: a
    # blind restart of one of these threads could have side effects
    # (e.g. re-firing a reminder mid-cycle) this watchdog can't reason
    # about safely, so it logs + emits a structured event and leaves
    # recovery to a human or a future, better-informed mechanism.
    # ------------------------------------------------------------------

    def _check_background_workers(self):
        for name, mgr in self._background_managers.items():
            self._check_one_poll_worker(name, mgr)
        self._check_task_planner_stuck()

    def _check_one_poll_worker(self, name: str, mgr) -> None:
        thread = getattr(mgr, "_poll_thread", None)
        if thread is None:
            return  # never started (e.g. disabled in config) — not an error
        previous = self._worker_status.get(name)

        if not thread.is_alive():
            status = "dead"
        else:
            last_poll = getattr(mgr, "_last_poll_ts", 0.0)
            poll_interval = getattr(mgr, "poll_interval", None)
            if last_poll and poll_interval:
                stale_for = time.time() - last_poll
                status = "stuck" if stale_for > poll_interval * self._poll_stuck_multiplier else "healthy"
            else:
                status = "healthy"  # can't evaluate staleness — don't false-positive

        if status == previous:
            return
        self._worker_status[name] = status
        if status == "healthy":
            self.logger.info("Background worker '%s' recovered (was: %s)", name, previous)
        else:
            self.logger.warning("Background worker '%s' is %s", name, status)
            self._emit_event(
                "error_recovery", f"worker_{status}",
                f"Background worker '{name}' is {status}",
                severity="warn", metadata={"worker": name, "status": status},
            )

    def _check_task_planner_stuck(self) -> None:
        tp = self._task_planner
        if tp is None:
            return
        plan = getattr(tp, "active_plan", None)
        if plan is None:
            self._plan_step_seen = None
            self._plan_stuck_logged = False
            return
        running_step = next(
            (s for s in plan.steps if getattr(s.status, "value", s.status) == "running"),
            None,
        )
        if running_step is None:
            self._plan_step_seen = None
            self._plan_stuck_logged = False
            return

        key = (id(plan), running_step.step_id)
        now = time.monotonic()
        if self._plan_step_seen is None or self._plan_step_seen[0] != key:
            self._plan_step_seen = (key, now)
            self._plan_stuck_logged = False
            return

        stuck_for = now - self._plan_step_seen[1]
        if stuck_for > self._command_hung_threshold:
            if not self._plan_stuck_logged:
                self._plan_stuck_logged = True
                self.logger.warning(
                    "TaskPlanner step %d ('%s') has been running for %.0fs — possible stuck step",
                    running_step.step_id, running_step.description, stuck_for,
                )
                self._emit_event(
                    "error_recovery", "task_planner_step_stuck",
                    f"Plan step {running_step.step_id} stuck for {stuck_for:.0f}s",
                    severity="warn",
                    metadata={
                        "step_id": running_step.step_id,
                        "skill_name": running_step.skill_name,
                        "stuck_for_s": round(stuck_for, 1),
                    },
                )

    def get_background_health(self) -> dict:
        """Snapshot of background-worker visibility state — for a future
        system_health integration or direct inspection. Metadata only
        (status strings, ids, durations), never user content."""
        tp = self._task_planner
        plan_info = None
        if tp is not None:
            plan = getattr(tp, "active_plan", None)
            if plan is not None:
                running_step = next(
                    (s for s in plan.steps if getattr(s.status, "value", s.status) == "running"),
                    None,
                )
                plan_info = {
                    "status": getattr(plan.status, "value", str(plan.status)),
                    "running_step_id": running_step.step_id if running_step else None,
                    "stuck": self._plan_stuck_logged,
                }
        return {
            "workers": dict(self._worker_status),
            "task_planner": plan_info,
        }

    # ------------------------------------------------------------------
    # Recovery cooldown
    # ------------------------------------------------------------------

    def _can_recover(self, check_name: str) -> bool:
        last = self._recovery_log.get(check_name, 0.0)
        return (time.monotonic() - last) >= self._recovery_cooldown

    def _record_recovery(self, check_name: str):
        self._recovery_log[check_name] = time.monotonic()

    # ------------------------------------------------------------------
    # TTS announcements (rate-limited)
    # ------------------------------------------------------------------

    def _can_announce(self) -> bool:
        if not self._announce_failures:
            return False
        now = time.monotonic()
        self._announcement_times = [
            t for t in self._announcement_times if now - t < 3600
        ]
        return len(self._announcement_times) < self._max_announcements_per_hour

    def _announce(self, message: str):
        if not self._can_announce():
            self.logger.warning("Suppressed announcement (rate limit): %s", message)
            return
        self._announcement_times.append(time.monotonic())
        self.logger.info("Announcing: %s", message)
        self._tts_queue.put(Event(
            EventType.SPEAK_REQUEST,
            data={"text": message},
            source="watchdog",
        ))

    # ------------------------------------------------------------------
    # Structured event logging
    # ------------------------------------------------------------------

    def _emit_recovery(self, check_name: str, message: str,
                       metadata: dict = None):
        """Emit a structured error_recovery event for a watchdog intervention."""
        self._emit_event(
            "error_recovery", f"watchdog_{check_name}",
            message, severity="warn", metadata=metadata,
        )

    def _emit_event(self, category: str, event: str, message: str,
                    severity: str = "info", metadata: dict = None):
        """Emit a structured event (best-effort, never raises)."""
        try:
            from core.event_logger import get_event_logger
            el = get_event_logger()
            if el:
                el.emit(
                    category=category,
                    event=event,
                    message=message,
                    severity=severity,
                    source="watchdog",
                    metadata=metadata,
                )
        except Exception:
            pass  # Event logging must never break the watchdog
