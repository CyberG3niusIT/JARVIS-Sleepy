"""VisionGate: optional, strictly gated forwarding of ONE presence frame to the primary LLM.

Design rules (privacy first):
  * Default OFF (``vision.presence.llm_gate.enabled``).
  * Needs PrivacyGate WEBCAM_CAPTURE + PROACTIVE_OBSERVATION (+ CLOUD_LLM if the route is cloud).
  * One frame per relevant event (DETECTED transition / MOTION), with a cooldown; never continuous.
  * Frames live in RAM only: no file, no save_tool_image, no persistence.
  * The returned text is NOT spoken here; the caller decides.
"""

from __future__ import annotations

import base64
import inspect
import threading
import time
from typing import Callable, Optional

from core.logger import get_logger
from core.privacy_gate import Capability, get_privacy_gate

try:  # cv2 is optional (tests / headless)
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None

MAX_WIDTH = 1280
DEFAULT_EVENTS = ("DETECTED", "MOTION")

_SYSTEM_CONTEXT = (
    "Du bekommst EIN einzelnes Kamerabild als Anwesenheits-Kontext (kein Video, keine Speicherung). "
    "Beschreibe in hoechstens zwei kurzen Saetzen sachlich, was fuer Anwesenheit/Situation relevant ist "
    "(z.B. Person am Schreibtisch, Raum leer). Keine Identifikation von Personen, keine Spekulation."
)


class VisionGate:
    def __init__(self, config=None, route_is_cloud: Optional[Callable[[], bool]] = None):
        cfg = {}
        if config is not None and hasattr(config, "get"):
            cfg = config.get("vision.presence.llm_gate", {}) or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.cooldown_s = float(cfg.get("cooldown_s", 120))
        self.events = tuple(str(e).upper() for e in (cfg.get("events") or DEFAULT_EVENTS))
        self._route_is_cloud = route_is_cloud
        self._lock = threading.Lock()
        self._last_forward: Optional[float] = None
        self.forwarded = 0
        self.suppressed: dict[str, int] = {}
        self.last_error: Optional[str] = None
        self.logger = get_logger("vision_gate", config)

    # ------------------------------------------------------------------
    def _suppress(self, reason: str) -> tuple[bool, str]:
        with self._lock:
            self.suppressed[reason] = self.suppressed.get(reason, 0) + 1
        return False, reason

    def should_forward(self, event: str, conversation_active: bool = False,
                       now: Optional[float] = None) -> tuple[bool, str]:
        """Decide whether one frame may be forwarded now. Does not consume the cooldown."""
        now = time.time() if now is None else now
        if not self.enabled:
            return self._suppress("disabled")
        if str(event).upper() not in self.events:
            return self._suppress("event_not_relevant")
        try:
            gate = get_privacy_gate()
            if not gate.allow(Capability.WEBCAM_CAPTURE):
                return self._suppress("privacy_webcam")
            if not gate.allow(Capability.PROACTIVE_OBSERVATION):
                return self._suppress("privacy_proactive_observation")
            if self._route_is_cloud is not None and self._route_is_cloud():
                if not gate.allow(Capability.CLOUD_LLM):
                    return self._suppress("privacy_cloud_llm")
        except Exception as e:  # fail closed
            self.logger.debug(f"privacy gate check failed: {e}")
            return self._suppress("privacy_gate_error")
        if conversation_active:
            return self._suppress("conversation_active")
        with self._lock:
            last = self._last_forward
        if last is not None and now - last < self.cooldown_s:
            return self._suppress("cooldown")
        return True, "ok"

    # ------------------------------------------------------------------
    def select_frame(self, frame_bgr) -> Optional[str]:
        """Encode one frame as base64 PNG in memory (downscaled to <=1280 wide). None on failure."""
        if cv2 is None or frame_bgr is None:
            return None
        try:
            h, w = frame_bgr.shape[:2]
            if w > MAX_WIDTH:
                scale = MAX_WIDTH / float(w)
                frame_bgr = cv2.resize(frame_bgr, (MAX_WIDTH, max(1, int(h * scale))),
                                       interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".png", frame_bgr)
            if not ok:
                return None
            return base64.b64encode(buf.tobytes()).decode("ascii")
        except Exception as e:
            self.logger.debug(f"frame encode failed: {e}")
            return None

    def _primary_not_ready(self, llm_router) -> Optional[str]:
        """Suppression reason if the primary cannot take the frame now (handover swap / not READY)."""
        try:
            from core import runtime_state
            if runtime_state.handover_in_progress():
                return "primary_swapping"
        except Exception:
            pass
        probe = getattr(llm_router, "probe_role", None)
        if callable(probe):
            try:
                if probe("primary") != "READY":
                    return "primary_not_ready"
            except Exception:
                return "primary_not_ready"
        return None

    def forward(self, frame, event: str, llm_router, conversation_active: bool = False,
                now: Optional[float] = None) -> Optional[str]:
        """Gate check + send exactly one frame; returns the model text (not spoken) or None."""
        now = time.time() if now is None else now
        ok, _reason = self.should_forward(event, conversation_active, now)
        if not ok or llm_router is None:
            if ok:
                self._suppress("no_llm_router")
            return None
        not_ready = self._primary_not_ready(llm_router)
        if not_ready:
            self._suppress(not_ready)  # the frame is dropped, never queued or retried
            return None
        b64 = self.select_frame(frame)
        if b64 is None:
            self._suppress("frame_unavailable")
            return None
        with self._lock:  # claim the cooldown before the (slow) call: one frame per event
            self._last_forward = now
        kwargs = {"image_data": b64}
        try:
            params = inspect.signature(llm_router.chat).parameters
            if "role" in params:
                kwargs["role"] = "primary"
        except (TypeError, ValueError):
            pass
        try:
            text = llm_router.chat(f"{_SYSTEM_CONTEXT}\n\nEreignis: {event}", **kwargs)
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"[:200]
            self.logger.warning(f"vision gate forward failed: {self.last_error}")
            return None
        finally:
            b64 = None
        with self._lock:
            self.forwarded += 1
        return text

    def status(self) -> dict:
        with self._lock:
            return {
                "enabled": self.enabled,
                "cooldown_s": self.cooldown_s,
                "events": list(self.events),
                "forwarded": self.forwarded,
                "suppressed": dict(self.suppressed),
                "last_forward": self._last_forward,
                "last_error": self.last_error,
                "persistence": "none",
            }
