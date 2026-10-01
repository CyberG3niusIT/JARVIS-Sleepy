"""
Presence Detector — continuous face detection and identification.

Uses InsightFace (RetinaFace detection + ArcFace 512-dim recognition) for
both detection and identification in a single pass. 99.83% LFW accuracy.

Fires proactive greetings when known people appear, following the
reminder_manager background thread + EventTTSProxy pattern.
"""

import asyncio
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from core.logger import get_logger
from core.honorific import set_honorific
from core.npu_face_backend import NpuFaceBackend, NpuUnavailable
from core.vision_gate import VisionGate


# Singleton
_instance: Optional["PresenceDetector"] = None


def get_presence_detector(config=None, tts=None, webcam_manager=None,
                          people_manager=None, conversation=None,
                          reminder_manager=None) -> Optional["PresenceDetector"]:
    """Get or create the singleton PresenceDetector."""
    global _instance
    if _instance is None and config is not None:
        _instance = PresenceDetector(
            config, tts, webcam_manager, people_manager,
            conversation, reminder_manager,
        )
    return _instance


class PresenceState(Enum):
    ABSENT = auto()
    DETECTED = auto()
    GREETED = auto()
    PRESENT = auto()


@dataclass
class PersonPresence:
    person_id: Optional[str]  # None = unknown face
    state: PresenceState = PresenceState.ABSENT
    first_seen: float = 0.0
    last_seen: float = 0.0
    last_greeted: float = 0.0
    confidence: float = 0.0


class PresenceDetector:
    """Continuous face detection engine with proactive greetings."""

    def __init__(self, config, tts, webcam_manager, people_manager,
                 conversation, reminder_manager=None):
        self.config = config
        self.tts = tts
        self._webcam_manager = webcam_manager
        self._people_manager = people_manager
        self.conversation = conversation
        self._reminder_manager = reminder_manager
        self.logger = get_logger("presence", config)

        # Config
        presence_cfg = config.get("vision.presence", {}) if hasattr(config, 'get') else {}
        self._interval = presence_cfg.get("detection_interval", 10)
        self._cooldown = presence_cfg.get("greeting_cooldown", 7200)
        self._confidence_threshold = presence_cfg.get("face_confidence_threshold", 0.6)
        self._min_face_size = presence_cfg.get("min_face_size", 80)
        self._greet_unknown = presence_cfg.get("greet_unknown", False)
        self._absence_threshold = presence_cfg.get("absence_threshold", 30)

        # Face embeddings directory
        self._embeddings_dir = Path(
            config.get("system.storage_path", "/home/alex/jarvis-data")
        ) / "data" / "face_embeddings"
        self._embeddings_dir.mkdir(parents=True, exist_ok=True)

        # State tracking
        self._person_states: dict[str, PersonPresence] = {}
        self._face_cache: dict[str, np.ndarray] = {}  # person_id -> 512-dim encoding
        self._face_user_map: dict[str, str] = {}      # person_id -> user_id (for identity propagation)

        # InsightFace app (lazy-loaded). Backend: "cpu" (default, InsightFace on
        # onnxruntime), "npu" (Intel NPU via the Windows OpenVINO worker) or
        # "auto" (NPU if usable, else CPU). See core/npu_face_backend.py.
        self._face_app = None
        self._backend_requested = str(presence_cfg.get("backend", "cpu")).lower()
        if self._backend_requested not in ("cpu", "npu", "auto"):
            self.logger.warning(
                f"Unknown vision.presence.backend '{self._backend_requested}' — using cpu"
            )
            self._backend_requested = "cpu"
        self._npu_cfg = presence_cfg.get("npu", {}) or {}
        self._npu_fallback_to_cpu = bool(self._npu_cfg.get("fallback_to_cpu", True))
        self._npu_disabled = False  # set after an NPU init/runtime failure
        self._backend_info: dict = {"requested": self._backend_requested, "active": None, "reason": None}
        # Similarities of the most recent identification pass (transparency only)
        self.last_matches: list[dict] = []
        self._camera_idle_logged = False
        self._privacy_skip_logged = False
        self._last_npu_sensor: Optional[tuple] = None
        # Optional LLM vision gate (default OFF; see core/vision_gate.py)
        self._vision_gate = VisionGate(config)
        self._event_frame = None          # frame of the current poll, RAM only, cleared after use
        self._vision_thread: Optional[threading.Thread] = None
        self.last_vision_note: Optional[str] = None

        # Callbacks (set by jarvis_continuous.py)
        self._pause_listener_callback: Optional[Callable] = None
        self._resume_listener_callback: Optional[Callable] = None
        self._window_callback: Optional[Callable] = None
        self._conv_state = None  # ConversationState (set post-init for window_source tagging)
        self._accumulator = None  # AwarenessAccumulator (set post-init for precompute)
        self._llm_router = None   # LLMRouter (set post-init for ambient briefing composition)

        # Thread control
        self._running = False
        self._stop_event = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None

        # Load existing face embeddings
        self._load_face_embeddings()

        self.logger.info(
            f"Presence detector initialized "
            f"({len(self._face_cache)} enrolled faces, "
            f"interval={self._interval}s, cooldown={self._cooldown}s)"
        )

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------

    def _get_face_app(self):
        """Lazy-load the face pipeline (NPU backend or CPU InsightFace).

        Both expose ``.get(frame_bgr) -> [face]`` with ``bbox`` and
        ``normed_embedding``.
        """
        if self._face_app is None:
            self._face_app = self._create_face_app()
        return self._face_app

    def _create_face_app(self):
        """Pick the backend. The NPU path never falls back silently: a failure
        is logged, recorded in ``get_status()['backend']`` and (unless
        ``vision.presence.npu.fallback_to_cpu`` is false) the CPU path is used."""
        if self._npu_disabled and self._backend_requested == "npu" and not self._npu_fallback_to_cpu:
            # Sticky until restart: never slip into CPU when the operator forbade it
            raise NpuUnavailable(self._backend_info.get("reason") or "npu_disabled")
        if self._backend_requested in ("npu", "auto") and not self._npu_disabled:
            try:
                backend = self._create_npu_backend()
                info = backend.initialize()
                self._backend_info = {
                    "requested": self._backend_requested, "active": "npu", "reason": None,
                    "execution_devices": info.get("execution_devices"),
                    "npu_name": info.get("npu_name"), "openvino": info.get("openvino"),
                }
                self.logger.info(f"Presence backend: NPU {info.get('execution_devices')}")
                return backend
            except NpuUnavailable as e:
                self._npu_disabled = True
                self._backend_info = {
                    "requested": self._backend_requested, "active": None,
                    "reason": e.code, "detail": e.detail[:300],
                }
                if self._backend_requested == "npu" and not self._npu_fallback_to_cpu:
                    self.logger.error(f"NPU presence backend unavailable ({e.code}); CPU fallback disabled")
                    raise
                log = self.logger.warning if self._backend_requested == "npu" else self.logger.info
                log(f"NPU presence backend unavailable ({e.code}) — falling back to CPU InsightFace")
        app = self._create_cpu_face_app()
        self._backend_info = dict(self._backend_info, requested=self._backend_requested, active="cpu")
        return app

    def _create_npu_backend(self) -> NpuFaceBackend:
        storage = self.config.get("system.storage_path", "/home/alex/jarvis-data")
        model_dir = self._npu_cfg.get("model_dir") or str(
            Path(storage) / "models" / "insightface" / "buffalo_l"
        )
        windows_python = os.environ.get("JARVIS_NPU_WINDOWS_PYTHON") or self._npu_cfg.get("windows_python", "")
        return NpuFaceBackend(
            model_dir=model_dir,
            windows_python=windows_python,
            timeout=float(self._npu_cfg.get("request_timeout", 30)),
            logger=self.logger,
        )

    def _create_cpu_face_app(self):
        self.logger.info("Loading InsightFace buffalo_l...")
        import warnings
        warnings.filterwarnings("ignore", message=".*estimate.*is deprecated.*")
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))
        self.logger.info("InsightFace loaded")
        return app

    def _analyse(self, frame):
        """``app.get(frame)`` with a visible fallback if the NPU worker dies mid-run."""
        try:
            app = self._get_face_app()
        except NpuUnavailable:
            return []  # backend: npu with fallback_to_cpu=false — state is in get_status()['backend']
        try:
            return app.get(frame)
        except NpuUnavailable as e:
            self.logger.warning(f"NPU presence backend failed at runtime ({e.code})")
            self._npu_disabled = True
            self._backend_info = {
                "requested": self._backend_requested, "active": None,
                "reason": e.code, "detail": e.detail[:300],
            }
            try:
                app.close()
            except Exception:
                pass
            self._face_app = None
            if self._backend_requested == "npu" and not self._npu_fallback_to_cpu:
                return []
            return self._get_face_app().get(frame)

    def ensure_backend(self) -> dict:
        """Initialise the face backend now (no camera needed) and return its status."""
        self._get_face_app()
        return dict(self._backend_info)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Launch the background polling thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="presence-detector"
        )
        self._poll_thread.start()
        self.logger.info("Presence detection started")

    def stop(self):
        """Stop the polling thread."""
        self._running = False
        self._stop_event.set()
        if self._poll_thread:
            self._poll_thread.join(timeout=10)
        if isinstance(self._face_app, NpuFaceBackend):
            self._face_app.close()  # ends the Windows worker process
            self._face_app = None
        self.logger.info("Presence detection stopped")

    def set_listener_callbacks(self, pause: Callable, resume: Callable):
        """Set callbacks for pausing/resuming the listener during greetings."""
        self._pause_listener_callback = pause
        self._resume_listener_callback = resume

    def set_window_callback(self, callback: Callable):
        """Set callback for opening a conversation window after greeting."""
        self._window_callback = callback

    def set_conv_state(self, conv_state):
        """Set conversation state for window_source tagging (CAL integration)."""
        self._conv_state = conv_state

    def set_accumulator(self, accumulator):
        """Set awareness accumulator for precompute on detection (CAL integration)."""
        self._accumulator = accumulator

    def set_llm_router(self, llm_router):
        """Set LLM router for ambient awareness briefing composition."""
        self._llm_router = llm_router

    # ------------------------------------------------------------------
    # Detection loop
    # ------------------------------------------------------------------

    def _poll_loop(self):
        """Main loop: detect faces every interval seconds."""
        # Delay first check to let audio/webcam initialize
        if self._stop_event.wait(5):
            return

        while self._running:
            try:
                if self._should_skip():
                    self._publish_npu_sensor()
                    if self._stop_event.wait(self._interval):
                        return
                    continue

                self._check_presence()

            except Exception as e:
                self.logger.error(f"Presence poll error: {e}", exc_info=True)

            self._publish_npu_sensor()  # heartbeat for the runtime probe (skip/no-camera cycles too)
            if self._stop_event.wait(self._interval):
                return

    def _should_skip(self) -> bool:
        """Skip detection during active conversation or TTS playback."""
        # Skip if conversation is active (don't interrupt)
        if hasattr(self.conversation, 'conversation_active') and \
                self.conversation.conversation_active:
            return True

        # Skip if no webcam available
        if not self._webcam_available():
            # Logged once per outage (the detector idles indefinitely without a camera)
            log = self.logger.debug if self._camera_idle_logged else self.logger.info
            log("Presence poll: webcam not available, skipping")
            self._camera_idle_logged = True
            return True

        self._camera_idle_logged = False
        return False

    def _webcam_available(self) -> bool:
        """Check if the desktop webcam is accessible."""
        if self._webcam_manager is None:
            return False
        return self._webcam_manager.device_available

    # ------------------------------------------------------------------
    # Frame capture (sync bridge for background thread)
    # ------------------------------------------------------------------

    def _grab_frame(self) -> Optional[np.ndarray]:
        """Grab a frame from the webcam and decode to numpy array."""
        try:
            wm = self._webcam_manager
            loop = wm._loop

            if loop and loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    wm.get_frame(timeout=5.0), loop
                )
                jpeg_bytes = future.result(timeout=8.0)
            else:
                # No event loop — can't grab frame
                return None

            # Decode JPEG to numpy BGR array
            arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            self._privacy_skip_logged = False
            return frame

        except PermissionError as e:
            # Webcam privacy gate: a quiet skip, logged once per privacy period
            if not self._privacy_skip_logged:
                self.logger.debug(f"Frame grab skipped (privacy gate): {e}")
                self._privacy_skip_logged = True
            return None
        except (TimeoutError, RuntimeError, FileNotFoundError) as e:
            self.logger.debug(f"Frame grab failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected frame grab error: {e}")
            return None

    # ------------------------------------------------------------------
    # Face detection + identification (single-pass with InsightFace)
    # ------------------------------------------------------------------

    def _detect_and_identify(self, frame: np.ndarray) -> list[tuple[Optional[str], float]]:
        """Detect all faces and identify them in a single pass.

        Returns list of (person_id, confidence) tuples.
        person_id is None for unknown faces.
        """
        faces = self._analyse(frame)
        self.last_matches = []

        if not faces:
            return []

        results = []
        for face in faces:
            # Filter by face size
            bbox = face.bbox.astype(int)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w < self._min_face_size or h < self._min_face_size:
                continue

            # If no enrolled faces, report as unknown
            if not self._face_cache:
                results.append((None, 0.0))
                continue

            # Get 512-dim ArcFace embedding
            embedding = face.normed_embedding  # Already L2-normalized

            # Compare against enrolled faces via cosine similarity
            best_match: Optional[str] = None
            best_score = -1.0

            for person_id, enrolled_emb in self._face_cache.items():
                score = float(np.dot(embedding, enrolled_emb))
                if score > best_score:
                    best_score = score
                    best_match = person_id

            # Transparency: similarity and the threshold actually applied.
            # The threshold is a configured value, NOT a calibrated identity
            # threshold (see docs); never authorise anything on it alone.
            self.last_matches.append({
                "person_id": best_match,
                "similarity": best_score,
                "threshold": self._confidence_threshold,
                "threshold_validated": False,
                "matched": best_score >= self._confidence_threshold,
            })

            if best_score >= self._confidence_threshold:
                results.append((best_match, best_score))
            else:
                results.append((None, best_score))

        return results

    # ------------------------------------------------------------------
    # Presence checking + state machine
    # ------------------------------------------------------------------

    def _check_presence(self):
        """Main detection cycle: grab frame → detect+identify → greet."""
        frame = self._grab_frame()
        if frame is None:
            if not self._privacy_skip_logged:
                self.logger.info("Presence poll: no frame (webcam unavailable)")
            self._publish_npu_sensor()
            return

        # Single-pass detection + identification
        face_results = self._detect_and_identify(frame)
        self._event_frame = frame  # only for the gated DETECTED hook below
        try:
            self._check_presence_results(face_results)
        finally:
            self._event_frame = None
            self._publish_npu_sensor()

    def _check_presence_results(self, face_results):

        if not face_results:
            if getattr(self, '_last_face_count', 0) > 0:
                self.logger.info("No faces detected")
                self._last_face_count = 0
            self._update_all_absent()
            return

        # Only log face count on change (avoid flooding every 10s)
        face_count = len(face_results)
        if face_count != getattr(self, '_last_face_count', 0):
            self.logger.info(f"Detected {face_count} face(s)")
            self._last_face_count = face_count

        now = time.time()
        seen_ids = set()

        for person_id, confidence in face_results:
            if person_id:
                seen_ids.add(person_id)
                self._handle_detection(person_id, confidence, now)
            elif not self._greet_unknown:
                # Unknown face — silent
                self.logger.info(f"Unknown face detected (confidence={confidence:.2f})")

        # Mark unseen people as absent
        for pid in list(self._person_states.keys()):
            if pid not in seen_ids:
                state = self._person_states[pid]
                if state.state != PresenceState.ABSENT:
                    # Check if they've been gone long enough
                    if now - state.last_seen > self._absence_threshold:
                        state.state = PresenceState.ABSENT
                        self.logger.info(f"Person {pid} → ABSENT")

        # CAL Phase 6: Ambient awareness — check for critical items when
        # user is PRESENT, not in active conversation, pipeline is idle.
        # Only safety/critical items (score >= 0.85) warrant unprompted speech.
        self._check_ambient_awareness(seen_ids, now)

    def _handle_detection(self, person_id: str, confidence: float, now: float):
        """State machine: manage transitions and fire greetings."""
        if person_id not in self._person_states:
            self._person_states[person_id] = PersonPresence(
                person_id=person_id,
                state=PresenceState.ABSENT,
            )

        state = self._person_states[person_id]
        state.last_seen = now
        state.confidence = confidence

        if state.state == PresenceState.ABSENT:
            # Transition: ABSENT → DETECTED
            state.state = PresenceState.DETECTED
            state.first_seen = now
            self.logger.info(
                f"Person {person_id} detected (confidence={confidence:.2f})"
            )
            self._maybe_vision_gate("DETECTED", now)

            # Precompute awareness items while greeting TTS plays
            user_id = self._face_user_map.get(person_id, "primary_user")
            if self._accumulator:
                try:
                    count = self._accumulator.refresh(user_id)
                    self.logger.info(f"Awareness precompute: {count} items for {user_id}")
                except Exception as e:
                    self.logger.warning(f"Awareness precompute failed: {e}")

            # Check if we should greet
            if self._greeting_allowed(person_id, now):
                was_long_absence = self._was_long_absence(person_id, now)
                self._fire_greeting(person_id, was_long_absence)
                state.state = PresenceState.GREETED
                state.last_greeted = now
            else:
                # Cooldown active — skip straight to PRESENT
                state.state = PresenceState.PRESENT

        elif state.state == PresenceState.DETECTED:
            # Already detected, waiting — transition to PRESENT
            state.state = PresenceState.PRESENT

        elif state.state == PresenceState.GREETED:
            # Already greeted — transition to PRESENT
            state.state = PresenceState.PRESENT

        # PRESENT stays PRESENT until they leave

    def _maybe_vision_gate(self, event: str, now: float):
        """Forward ONE frame to the primary LLM if the (default-off) vision gate allows it."""
        frame = self._event_frame
        if frame is None or not self._vision_gate.enabled:
            return
        conv_active = bool(getattr(self.conversation, "conversation_active", False))
        ok, _reason = self._vision_gate.should_forward(event, conv_active, now)
        if not ok or self._llm_router is None:
            return
        snapshot = frame.copy()

        def _run():
            self.last_vision_note = self._vision_gate.forward(
                snapshot, event, self._llm_router, conv_active, now)

        self._vision_thread = threading.Thread(target=_run, daemon=True, name="presence-vision-gate")
        self._vision_thread.start()

    def _check_ambient_awareness(self, seen_ids: set, now: float):
        """CAL Phase 6: Ambient awareness — speak critical items unprompted.

        Only fires when:
        - An identified user is in PRESENT state (not DETECTED/GREETED/ABSENT)
        - Accumulator is wired
        - Conversation window is NOT active (don't interrupt)
        - At least 60s since last ambient delivery (prevent spam)
        """
        if not self._accumulator:
            return

        # Don't interrupt active conversations
        if hasattr(self.conversation, 'conversation_active') and \
                self.conversation.conversation_active:
            return

        # Cooldown: at least 60s between ambient deliveries
        last_ambient = getattr(self, '_last_ambient_ts', 0)
        if now - last_ambient < 60:
            return

        # Find a PRESENT identified user
        for pid in seen_ids:
            state = self._person_states.get(pid)
            if not state or state.state != PresenceState.PRESENT:
                continue

            user_id = self._face_user_map.get(pid, "")
            if not user_id:
                continue

            # Check for critical items
            critical = self._accumulator.get_critical(user_id)
            if not critical:
                continue

            # Speak the critical item
            from core.awareness_accumulator import compose_briefing
            from core.honorific import get_honorific, set_honorific

            # Ensure correct honorific for this user
            # (may have been reset since greeting)
            set_honorific("sir" if user_id == "primary_user" else "ma'am")

            briefing = compose_briefing(
                critical, self._llm_router,
                honorific=get_honorific(),
                user_name=user_id.capitalize(),
                moment_type="ambient",
            )

            if briefing:
                self.logger.info(
                    "CAL ambient: critical item for %s → '%s'",
                    user_id, briefing[:80],
                )

                if self._pause_listener_callback:
                    self._pause_listener_callback()

                self.tts.speak(briefing)

                if self._resume_listener_callback:
                    self._resume_listener_callback()

                self._accumulator.mark_surfaced(critical, user_id)
                self._last_ambient_ts = now

                # Open a brief window so user can respond
                if self._window_callback:
                    self._window_callback(6.0)

            # Only one ambient delivery per cycle
            break

    def _update_all_absent(self):
        """Mark all tracked people as absent if they've been gone long enough."""
        now = time.time()
        for pid, state in self._person_states.items():
            if state.state != PresenceState.ABSENT:
                if now - state.last_seen > self._absence_threshold:
                    state.state = PresenceState.ABSENT
                    self.logger.info(f"Person {pid} → ABSENT (no faces detected)")

    def _greeting_allowed(self, person_id: str, now: float) -> bool:
        """Check cooldown: only greet once per cooldown period."""
        state = self._person_states.get(person_id)
        if state and state.last_greeted > 0:
            return (now - state.last_greeted) > self._cooldown
        return True  # Never greeted before

    def _was_long_absence(self, person_id: str, now: float) -> bool:
        """Check if this person was absent for >30 minutes (return greeting)."""
        state = self._person_states.get(person_id)
        if state and state.last_greeted > 0:
            # Use last_greeted as proxy for last known presence
            return (now - state.last_greeted) > 1800  # 30 minutes
        return False  # First detection ever — not a "return"

    # ------------------------------------------------------------------
    # Greeting delivery
    # ------------------------------------------------------------------

    def _fire_greeting(self, person_id: str, is_return: bool = False):
        """Speak a presence greeting. Follows reminder_manager._fire_reminder() pattern."""
        from core.persona import presence_greeting, _time_of_day

        # Propagate face identity to conversation (so voice pipeline inherits it)
        user_id = self._face_user_map.get(person_id, "")
        if user_id and self.conversation:
            self.conversation.current_user = user_id
            self.logger.info(f"Face ID → current_user={user_id}")

        # Restore owner honorific for greeting
        set_honorific("sir")

        # Check for pending reminders (for return-with-reminders greeting)
        has_pending = False
        if is_return and self._reminder_manager:
            try:
                pending = self._reminder_manager.get_pending_acks()
                has_pending = len(pending) > 0
            except Exception:
                pass

        # Build greeting
        tod = _time_of_day()
        greeting = presence_greeting(tod, is_return=is_return,
                                     has_pending_reminders=has_pending)

        self.logger.info(
            f"Greeting {person_id}: '{greeting}' "
            f"(return={is_return}, pending_reminders={has_pending})"
        )

        # Pause listening → speak → open conversation window
        if self._pause_listener_callback:
            self._pause_listener_callback()

        tts_ok = self.tts.speak(greeting)

        if self._resume_listener_callback:
            self._resume_listener_callback()

        # Tag the conversation window as presence-triggered (CAL integration)
        # Return-from-absence gets a distinct tag for different briefing budget
        if self._conv_state:
            self._conv_state.window_source = "presence_return" if is_return else "presence_greeting"

        # Open a conversation window so user can respond
        if self._window_callback:
            self._window_callback(8.0)

    # ------------------------------------------------------------------
    # Face enrollment
    # ------------------------------------------------------------------

    def enroll_face(self, person_id: str, frame_bytes: bytes,
                    person_name: str = "") -> tuple[bool, str]:
        """Extract face encoding from a single JPEG frame and save.

        For single-shot enrollment. Prefer enroll_face_multi() for better
        accuracy across angles and conditions (glasses, lighting).

        Returns:
            (success, message)
        """
        encoding = self._extract_encoding(frame_bytes)
        if isinstance(encoding, str):
            return False, encoding  # Error message

        self._save_encoding(person_id, encoding, person_name)
        name_label = person_name or person_id
        return True, f"Face enrolled successfully for {name_label}."

    def enroll_face_multi(self, person_id: str, frames: list[bytes],
                          person_name: str = "") -> tuple[bool, str]:
        """Extract face encodings from multiple frames and save the average.

        Multiple angles and conditions (glasses on/off) produce a more robust
        encoding that handles real-world variation better than a single shot.

        Args:
            person_id: ID from people_manager
            frames: List of JPEG byte frames
            person_name: Display name for logging

        Returns:
            (success, message) — message includes count of successful extractions
        """
        encodings = []
        errors = []
        for i, frame_bytes in enumerate(frames):
            result = self._extract_encoding(frame_bytes)
            if isinstance(result, str):
                errors.append(f"Frame {i + 1}: {result}")
                self.logger.debug("Enrollment frame %d failed: %s", i + 1, result)
            else:
                encodings.append(result)

        if not encodings:
            return False, "No faces could be extracted from any frame. Please try again."

        # Average all successful encodings and re-normalize
        avg_encoding = np.mean(encodings, axis=0)
        avg_encoding = avg_encoding / np.linalg.norm(avg_encoding)

        self._save_encoding(person_id, avg_encoding, person_name)
        name_label = person_name or person_id
        self.logger.info(
            f"Multi-image enrollment for {name_label}: "
            f"{len(encodings)}/{len(frames)} frames successful"
        )
        return True, (
            f"Face enrolled for {name_label} using {len(encodings)} images. "
            f"Recognition should work across different angles and conditions."
        )

    def _extract_encoding(self, frame_bytes: bytes):
        """Extract a single 512-dim face encoding from JPEG bytes.

        Returns numpy array on success, or error string on failure.
        """
        arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return "Could not decode the camera frame."

        faces = self._analyse(frame)
        if not faces:
            return "No face detected in the frame."

        if len(faces) > 1:
            return f"Multiple faces detected ({len(faces)}). Please ensure only one person is in frame."

        return faces[0].normed_embedding

    def _save_encoding(self, person_id: str, encoding, person_name: str = ""):
        """Save encoding to disk and update caches."""
        embed_path = self._embeddings_dir / f"face_{person_id}.npy"
        np.save(str(embed_path), encoding)

        self._face_cache[person_id] = encoding

        if self._people_manager:
            self._people_manager.set_face_embedding_path(
                person_id, str(embed_path)
            )

        name_label = person_name or person_id
        self.logger.info(
            f"Enrolled face for {name_label} "
            f"(saved to {embed_path}, {len(encoding)}-dim encoding)"
        )

    def _load_face_embeddings(self):
        """Load all enrolled face embeddings from disk."""
        loaded = 0
        if self._people_manager:
            people = self._people_manager.get_people_with_face_embeddings()
            for person in people:
                path = person.get("face_embedding_path")
                if path and Path(path).exists():
                    try:
                        encoding = np.load(path)
                        self._face_cache[person["person_id"]] = encoding
                        self._face_user_map[person["person_id"]] = person.get("user_id", "")
                        loaded += 1
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to load face embedding for "
                            f"{person['name']}: {e}"
                        )

        # Also check embeddings directory for .npy files not in DB
        for npy_path in self._embeddings_dir.glob("face_*.npy"):
            pid = npy_path.stem.replace("face_", "")
            if pid not in self._face_cache:
                try:
                    encoding = np.load(str(npy_path))
                    self._face_cache[pid] = encoding
                    loaded += 1
                    self.logger.debug(f"Loaded orphan embedding: {npy_path.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to load {npy_path}: {e}")

        if loaded:
            self.logger.info(f"Loaded {loaded} face embeddings")

    # ------------------------------------------------------------------
    # Status / introspection
    # ------------------------------------------------------------------

    def npu_sensor_status(self) -> dict:
        """Honest NPU sensor component state, derived only from real backend/camera state."""
        info = self._backend_info
        camera_ok = self._webcam_available()
        if not self._running and info.get("active") is None and not info.get("reason"):
            state, reason = "STOPPED", "presence detector not running / backend not initialised"
        elif info.get("active") == "npu":
            if camera_ok:
                state, reason = "READY", None
            else:
                state, reason = "DEGRADED", "camera_unavailable"
        elif info.get("active") == "cpu":
            state, reason = "DEGRADED", f"cpu_fallback: {info.get('reason') or 'npu_not_requested'}"
        elif info.get("reason"):
            state, reason = "DEGRADED", str(info.get("reason"))
        else:
            state, reason = "STOPPED", "backend not initialised"
        # Face pipeline may run on the NPU per frame, but wake signal and a continuous
        # live camera->NPU stream are not built: never claimed.
        return {"state": state, "reason": reason, "active": info.get("active"),
                "enabled": bool(self.config.get("vision.presence.enabled", True)) if hasattr(self.config, "get") else True,
                "wake_signal": "NOT_IMPLEMENTED", "live_camera_npu": "NOT_IMPLEMENTED"}

    def _publish_npu_sensor(self):
        """Report the sensor through the shared schema (core/runtime_state.write_npu_sensor).

        Written on change and republished every NPU_SENSOR_REPUBLISH_S even when unchanged, so
        the probe's freshness check never mistakes a steady sensor for a dead one (best effort).
        """
        try:
            from core import runtime_state
            sensor = self.npu_sensor_status()
            key = (sensor["state"], sensor["reason"], sensor["active"], sensor["enabled"])
            now = time.monotonic()
            last_at = getattr(self, "_last_npu_publish_at", None)
            if key == self._last_npu_sensor and last_at is not None \
                    and now - last_at < runtime_state.NPU_SENSOR_REPUBLISH_S:
                return
            self._last_npu_sensor = key
            self._last_npu_publish_at = now
            runtime_state.write_npu_sensor(sensor)
        except Exception:
            pass

    def get_status(self) -> dict:
        """Return current presence detection status for health check."""
        return {
            "npu_sensor": self.npu_sensor_status(),
            "vision_gate": self._vision_gate.status(),
            "running": self._running,
            "camera": "AVAILABLE" if self._webcam_available() else "UNAVAILABLE",
            "backend": dict(self._backend_info),
            "matching": {
                "metric": "cosine similarity of L2-normalised ArcFace embeddings",
                "threshold": self._confidence_threshold,
                "threshold_validated": False,
                "note": "configured value, not calibrated; do not use as sole authorisation",
            },
            "enrolled_faces": len(self._face_cache),
            "tracked_people": len(self._person_states),
            "interval": self._interval,
            "cooldown": self._cooldown,
            "states": {
                pid: {
                    "state": s.state.name,
                    "confidence": s.confidence,
                    "last_seen": s.last_seen,
                }
                for pid, s in self._person_states.items()
            },
        }
