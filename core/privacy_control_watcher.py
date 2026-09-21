"""Smallest-possible local control path for core.privacy_gate.PrivacyGate,
for entrypoints (jarvis_continuous.py in particular) that have no
interactive text input to run PrivacySkill's intents through.

Why this exists (session #6 finding): voice is NOT a reliable way to
exit PRIVACY. Once PrivacyGate.enter(PRIVACY) runs, MIC_INGEST and STT
are both denied (see core/continuous_listener.py) — meaning no spoken
audio is ever transcribed to text while privacy is active, so a spoken
"Privatsphäre beenden" can never reach PrivacySkill's intent matcher in
the first place. That's the deliberate, correct behavior of PRIVACY, not
a bug — but it means voice cannot be the exit mechanism, and building a
special STT bypass just for an exit phrase would mean privacy-mode audio
*is* being transcribed after all, defeating the guarantee. The task's own
instruction is explicit: "kein STT-Bypass."

PrivacySkill (skills/system/privacy/skill.py) already gives a reliable
non-audio control path wherever typed text reaches the skill router
(jarvis_console.py, jarvis_web.py's chat) — those never touch mic/STT at
all. But PrivacyGate is a **process-local singleton**: jarvis_continuous.py,
jarvis_console.py, and jarvis_web.py are three separate entrypoints/
processes (confirmed by reading each — every one constructs its own
ConversationManager etc.), so a PrivacySkill intent typed into a console
process would flip a *different* PrivacyGate instance than the one
actually governing a running jarvis_continuous.py daemon. jarvis_continuous.py
itself has no interactive text input at all (it's a headless daemon).

This watcher is the "kleinste sichere CLI" fallback the task explicitly
allows for exactly that case: a background thread polls three sentinel
files (existence-only, no content parsed — nothing to inject), and calls
the corresponding PrivacyGate method on the *same process's* singleton
when one appears, then deletes it.

Session #8 trust-boundary fix (agentic-audit finding #4): the sentinels
used to live directly under `/tmp` (matching core/debug_logger.py's own
`/tmp/.jarvis_debug_active` convention). `/tmp` is world-writable — any
local user on the same host, not just the one running jarvis, can
create a same-named file there. For debug_logger.py that only toggles a
diagnostic JSONL dump on, which is a much smaller blast radius than
privacy control: a same-named `/tmp/.jarvis_privacy_exit` created by
another local user, or planted in advance before jarvis starts, would
flip this process's actual privacy mode. On a genuinely single-user
device this is a theoretical concern, but the sentinel path costs
nothing to hold to a stricter standard, so it now resolves to a
user-private runtime directory instead (see `_default_runtime_dir()`):
$XDG_RUNTIME_DIR/jarvis or /run/user/$UID/jarvis (systemd-managed,
mode 0700, per-user — not shared with other users of the host) when
available, falling back to a dedicated /tmp/jarvis-$UID directory
(created here with mode 0700, ownership verified, symlinks refused)
only if neither exists. This is still a local-filesystem-access trust
boundary, not a new IPC layer — same polling mechanism, same three
sentinel files, just a directory only this user can write to.

Usage (from a shell on the same host running jarvis_continuous.py):
    touch "$XDG_RUNTIME_DIR/jarvis/.jarvis_privacy_enter"   # -> PrivacyMode.PRIVACY
    touch "$XDG_RUNTIME_DIR/jarvis/.jarvis_privacy_lock"    # -> PrivacyMode.PRIVACY_LOCK
    touch "$XDG_RUNTIME_DIR/jarvis/.jarvis_privacy_exit"    # -> PrivacyMode.NORMAL
    cat "$XDG_RUNTIME_DIR/jarvis/.jarvis_privacy_status"    # last known mode + timestamp
"""

import os
import stat
import threading
import time
from typing import Optional

from core.logger import get_logger
from core.privacy_gate import get_privacy_gate, PrivacyMode

logger = get_logger(__name__)


def _default_runtime_dir() -> str:
    """Resolve the user-private directory the privacy sentinel files
    live under. Prefers $XDG_RUNTIME_DIR/jarvis or /run/user/$UID/jarvis
    (systemd-managed, mode 0700, per-user tmpfs) over a self-created
    /tmp/jarvis-$UID fallback — the fallback is still validated
    (created 0700, ownership checked, symlinks refused) so a directory
    pre-planted by another local user is never trusted. Never raises:
    a broken/hostile environment degrades to plain /tmp (this module's
    previous behavior) with a loud warning, rather than crashing the
    watcher or blocking startup."""
    candidates = []
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        candidates.append(os.path.join(xdg, "jarvis"))
    run_user = f"/run/user/{os.getuid()}"
    if os.path.isdir(run_user):
        candidates.append(os.path.join(run_user, "jarvis"))
    candidates.append(f"/tmp/jarvis-{os.getuid()}")

    for path in candidates:
        try:
            os.makedirs(path, mode=0o700, exist_ok=True)
            os.chmod(path, 0o700)
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode):
                continue  # refuse a symlinked directory
            if st.st_uid != os.getuid():
                continue  # pre-created by someone else — don't trust it
            return path
        except OSError:
            continue

    logger.warning(
        "PrivacyControlWatcher: no user-private runtime dir available "
        "(tried XDG_RUNTIME_DIR/jarvis, /run/user/%s/jarvis, "
        "/tmp/jarvis-%s) — falling back to plain /tmp",
        os.getuid(), os.getuid(),
    )
    return "/tmp"


_RUNTIME_DIR = _default_runtime_dir()


class PrivacyControlWatcher(threading.Thread):
    """Polls for privacy control sentinel files. See module docstring."""

    ENTER_SENTINEL = os.path.join(_RUNTIME_DIR, ".jarvis_privacy_enter")
    LOCK_SENTINEL = os.path.join(_RUNTIME_DIR, ".jarvis_privacy_lock")
    EXIT_SENTINEL = os.path.join(_RUNTIME_DIR, ".jarvis_privacy_exit")
    STATUS_FILE = os.path.join(_RUNTIME_DIR, ".jarvis_privacy_status")

    DEFAULT_POLL_INTERVAL = 0.5  # seconds

    def __init__(self, config, poll_interval: float = None):
        super().__init__(daemon=True, name="privacy-control-watcher")
        self._gate = get_privacy_gate(config)
        self._poll_interval = poll_interval or self.DEFAULT_POLL_INTERVAL
        self._stop_event = threading.Event()
        self._gate.register_enter_callback(self._write_status)
        self._gate.register_exit_callback(self._write_status)

    def run(self) -> None:
        logger.info(
            "PrivacyControlWatcher started (poll=%.1fs): %s / %s / %s",
            self._poll_interval, self.ENTER_SENTINEL, self.LOCK_SENTINEL,
            self.EXIT_SENTINEL,
        )
        self._write_status(self._gate.mode())
        while not self._stop_event.is_set():
            # Session #7 fix: each _consume() call is a plain state
            # assignment (gate.enter()/exit()), so within one poll
            # iteration the LAST one applied is what the mode ends up
            # as — "checked last" and "wins" are opposite things, and
            # the previous order (LOCK, ENTER, EXIT — i.e. EXIT applied
            # last) actually made EXIT win any collision, the exact
            # opposite of the "protective outcome wins" comment that
            # used to be here (confirmed by the old
            # test_lock_wins_over_simultaneous_exit, which asserted
            # NORMAL as the outcome while its own docstring claimed
            # "lock wins" — the test and the comment were both
            # documenting the bug, not the intended behavior). To make
            # PRIVACY_LOCK > PRIVACY > EXIT actually hold when multiple
            # sentinels collide, the more protective state must be
            # applied LAST: EXIT first (weakest, overwritten by
            # anything after it), then ENTER, then LOCK (strongest,
            # applied last so it's the final state).
            self._consume(self.EXIT_SENTINEL, self._handle_exit)
            self._consume(self.ENTER_SENTINEL, self._handle_enter)
            self._consume(self.LOCK_SENTINEL, self._handle_lock)
            self._stop_event.wait(self._poll_interval)
        logger.info("PrivacyControlWatcher stopped")

    def stop(self) -> None:
        self._stop_event.set()

    # ---- sentinel handling ----

    def _consume(self, path: str, handler) -> None:
        if not os.path.exists(path):
            return
        try:
            os.remove(path)
        except OSError as e:
            logger.warning("PrivacyControlWatcher: failed to remove %s: %s", path, e)
            return  # don't act twice on the same sentinel if removal failed
        try:
            handler()
        except Exception:
            logger.exception("PrivacyControlWatcher: handler for %s failed", path)

    def _handle_enter(self) -> None:
        self._gate.enter(PrivacyMode.PRIVACY, actor="local_cli")

    def _handle_lock(self) -> None:
        self._gate.enter(PrivacyMode.PRIVACY_LOCK, actor="local_cli")

    def _handle_exit(self) -> None:
        self._gate.exit(actor="local_cli")

    # ---- status ----

    def _write_status(self, _mode: Optional[PrivacyMode] = None) -> None:
        """Registered as both enter- and exit-callback, so STATUS_FILE
        reflects the current mode regardless of what triggered the
        transition (voice/skill, this watcher, or any future caller) —
        metadata only (mode + timestamp), never content, matching
        PrivacyGate's own audit-log rule."""
        try:
            with open(self.STATUS_FILE, "w") as f:
                f.write(f"{self._gate.mode().value} {time.time():.3f}\n")
        except OSError as e:
            logger.warning("PrivacyControlWatcher: failed to write status file: %s", e)
