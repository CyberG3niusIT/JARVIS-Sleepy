"""Central privacy authority for JARVIS.

Before this module, "privacy" did not exist as a concept anywhere in the
backend: `continuous_listener._paused`/`_speaking_event` pause the mic only
to avoid TTS echo, `desktop_manager.toggle_mute()` controls speaker volume,
and `readback_session`/`task_planner` "paused" state is about resuming a
document read or a multi-step plan. None of those are privacy controls, and
none of them are touched by this module.

PrivacyGate is the single technical authority every ingestion, memory,
logging, and cloud/remote call site must consult before acting on user
data. It is intentionally not a collection of independent booleans: all
call sites ask `allow(capability)` (or `assert_allowed(capability)`) and
get an answer derived purely from `mode()`.

Usage::

    from core.privacy_gate import get_privacy_gate, Capability

    gate = get_privacy_gate(config)
    if not gate.allow(Capability.MIC_INGEST):
        return
    ...
    gate.assert_allowed(Capability.MEMORY_WRITE)  # raises PrivacyViolation

Race safety: `enter()`/`exit()` both (a) run registered flush callbacks
*before* changing anything else, so buffers are dropped under the same
lock that flips the mode, and (b) mint a new opaque `epoch()` token. Any
component that defers work to a background thread (batch/per-turn memory
extraction, consolidation, session summarization) must capture
`gate.epoch()` before starting and check `gate.is_current_epoch(captured)`
immediately before persisting anything. That is what prevents content
buffered/started before a privacy transition from being written after it
— a plain "is privacy active right now" boolean re-check at write time is
not sufficient, because the mode can flip (enter -> exit) between the
check and the write.
"""

import enum
import threading
import time
import uuid
from typing import Callable, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)

_instance: Optional["PrivacyGate"] = None
_instance_lock = threading.Lock()


def get_privacy_gate(config=None) -> "PrivacyGate":
    """Get or create the process-wide PrivacyGate singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PrivacyGate(config)
    return _instance


def reset_privacy_gate_singleton_for_tests() -> None:
    """Test-only: drop the singleton so the next get_privacy_gate() call
    creates a fresh instance. Never call this from production code."""
    global _instance
    with _instance_lock:
        _instance = None


class PrivacyMode(enum.Enum):
    NORMAL = "normal"
    PRIVACY = "privacy"
    PRIVACY_LOCK = "privacy_lock"


class Capability(enum.Enum):
    MIC_INGEST = "mic_ingest"
    STT = "stt"
    SCREEN_CAPTURE = "screen_capture"
    WEBCAM_CAPTURE = "webcam_capture"
    CLIPBOARD_READ = "clipboard_read"
    FILESYSTEM_OBSERVATION = "filesystem_observation"
    MEMORY_EXTRACT = "memory_extract"
    MEMORY_WRITE = "memory_write"
    EMBEDDING_GENERATE = "embedding_generate"
    SESSION_SUMMARY = "session_summary"
    AGENT_CONTEXT_INGEST = "agent_context_ingest"
    CLOUD_LLM = "cloud_llm"
    REMOTE_TOOL = "remote_tool"
    CONTENT_LOGGING = "content_logging"
    PROACTIVE_OBSERVATION = "proactive_observation"


# Everything that touches, derives from, or exfiltrates user content is
# blocked in PRIVACY. REMOTE_TOOL is deliberately left allowed here (e.g. a
# local-only tool invocation path may route through the same executor) —
# PRIVACY_LOCK is what closes that off unconditionally.
_PRIVACY_BLOCKED = frozenset({
    Capability.MIC_INGEST,
    Capability.STT,
    Capability.SCREEN_CAPTURE,
    Capability.WEBCAM_CAPTURE,
    Capability.CLIPBOARD_READ,
    Capability.FILESYSTEM_OBSERVATION,
    Capability.MEMORY_EXTRACT,
    Capability.MEMORY_WRITE,
    Capability.EMBEDDING_GENERATE,
    Capability.SESSION_SUMMARY,
    Capability.AGENT_CONTEXT_INGEST,
    Capability.CLOUD_LLM,
    Capability.CONTENT_LOGGING,
    Capability.PROACTIVE_OBSERVATION,
})

# PRIVACY_LOCK inherits every PRIVACY restriction and additionally closes
# all remote/external tool execution, regardless of whether that specific
# call would have touched protected content.
_PRIVACY_LOCK_BLOCKED = _PRIVACY_BLOCKED | frozenset({
    Capability.REMOTE_TOOL,
})


class PrivacyViolation(RuntimeError):
    """Raised by assert_allowed() when the current mode denies a capability."""


class PrivacyGate:
    """Process-wide privacy mode + capability authority. See module docstring."""

    def __init__(self, config=None):
        self._config = config
        self._lock = threading.RLock()
        self._mode = PrivacyMode.NORMAL
        self._epoch = uuid.uuid4().hex[:12]
        self._entered_at: Optional[float] = None
        self._flush_callbacks: List[Callable[[], None]] = []
        self._enter_callbacks: List[Callable[[PrivacyMode], None]] = []
        self._exit_callbacks: List[Callable[[], None]] = []

    # ---- state ----

    def mode(self) -> PrivacyMode:
        with self._lock:
            return self._mode

    def epoch(self) -> str:
        """Opaque token for the current privacy "generation". See module docstring."""
        with self._lock:
            return self._epoch

    def is_current_epoch(self, captured_epoch: str) -> bool:
        with self._lock:
            return captured_epoch == self._epoch

    # ---- callback registration ----
    # Ingestion/memory modules register here instead of this module importing
    # them, so privacy_gate has zero dependencies on the rest of core/.

    def register_flush_callback(self, fn: Callable[[], None]) -> None:
        """`fn` is invoked synchronously on both enter() and exit(), under
        the gate's lock, before the mode/epoch change is visible to other
        threads. Use it to drop ring buffers, pending extraction queues, or
        partial transcripts. Exceptions are logged, never propagated."""
        with self._lock:
            self._flush_callbacks.append(fn)

    def register_enter_callback(self, fn: Callable[[PrivacyMode], None]) -> None:
        with self._lock:
            self._enter_callbacks.append(fn)

    def register_exit_callback(self, fn: Callable[[], None]) -> None:
        with self._lock:
            self._exit_callbacks.append(fn)

    # ---- transitions ----

    def enter(self, mode: PrivacyMode, actor: str = "unknown", reason: str = "") -> None:
        if mode == PrivacyMode.NORMAL:
            raise ValueError("enter() requires PRIVACY or PRIVACY_LOCK; use exit() for NORMAL")
        with self._lock:
            for cb in list(self._flush_callbacks):
                try:
                    cb()
                except Exception:
                    logger.exception("privacy_gate: flush callback failed on enter")
            self._mode = mode
            self._epoch = uuid.uuid4().hex[:12]
            self._entered_at = time.monotonic()
            for cb in list(self._enter_callbacks):
                try:
                    cb(mode)
                except Exception:
                    logger.exception("privacy_gate: enter callback failed")
        # Metadata only — never log the reason text or any content.
        logger.info(
            "privacy.enter mode=%s actor=%s timestamp=%.3f",
            mode.value, actor, time.time(),
        )

    def exit(self, actor: str = "unknown") -> None:
        with self._lock:
            previous_mode = self._mode
            if previous_mode == PrivacyMode.NORMAL:
                return  # idempotent no-op
            duration = (
                time.monotonic() - self._entered_at
                if self._entered_at is not None else 0.0
            )
            # Flush again on exit: this is what guarantees no catch-up
            # ingestion of anything that accumulated while privacy was
            # active (capability denials should already have kept those
            # buffers empty, but this makes it unconditional).
            for cb in list(self._flush_callbacks):
                try:
                    cb()
                except Exception:
                    logger.exception("privacy_gate: flush callback failed on exit")
            self._mode = PrivacyMode.NORMAL
            self._epoch = uuid.uuid4().hex[:12]
            self._entered_at = None
            for cb in list(self._exit_callbacks):
                try:
                    cb()
                except Exception:
                    logger.exception("privacy_gate: exit callback failed")
        logger.info(
            "privacy.exit mode=%s actor=%s duration=%.3f timestamp=%.3f",
            previous_mode.value, actor, duration, time.time(),
        )

    # ---- checks ----

    def allow(self, capability: Capability) -> bool:
        with self._lock:
            mode = self._mode
        if mode == PrivacyMode.NORMAL:
            return True
        if mode == PrivacyMode.PRIVACY:
            return capability not in _PRIVACY_BLOCKED
        if mode == PrivacyMode.PRIVACY_LOCK:
            return capability not in _PRIVACY_LOCK_BLOCKED
        return False

    def assert_allowed(self, capability: Capability) -> None:
        if not self.allow(capability):
            raise PrivacyViolation(
                f"{capability.value} denied in mode={self.mode().value}"
            )
