"""Direct-audio voice turns (Gemma PRIMARY hears the audio itself).

With ``llm.primary.audio_direct`` the aggregated turn audio goes straight to the
primary model as an ``input_audio`` item. STT is NOT a prerequisite and never
delays or replaces the model input; it runs in parallel for wake-compat, the
stop/barge-in fast path and diagnostics. The ASR transcript is kept only as
``asr_hint`` metadata - never as the source of truth of the user turn.

Readiness (honest, no fake fallback):
  * primary READY                       -> request starts immediately
  * primary not READY + text fallback   -> caller runs the normal text path
    (only when a fallback provider is really configured/reachable)
  * primary not READY, no fallback      -> the turn is queued/waits with status
    STARTING (or DOWN); nothing pretends to answer.
"""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.speculative_turn import SpeculativeTurn

# Text part sent next to the audio item. The model hears the user; this only
# tells it what the audio is.
AUDIO_TURN_PROMPT = ("[Sprachaufnahme des Nutzers. Antworte auf das Gesprochene, "
                     "ausschließlich auf Deutsch.]")


@dataclass
class AudioTurn:
    turn_id: str
    turn: SpeculativeTurn
    mode: str                       # "direct" | "wait"
    gate_required: bool
    in_conversation: bool
    generation: Any = None
    audio: Any = None               # float32 16 kHz; dropped once encoded
    stream_handle: Any = field(default=None, repr=False)   # per-stream cancel handle (optional)
    audio_b64: Optional[str] = field(default=None, repr=False)  # in memory only (restart)
    placeholder: str = ""
    asr_hint: Optional[str] = None  # diagnostic metadata only
    failure: Optional[str] = None   # e.g. "primary_unavailable"
    context: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.monotonic)
    # STT verdict for ungated (conversation window) turns: the answer tokens are
    # buffered until the parallel STT transcript decided "direct" (release),
    # "text" (skill/tool/canned turn -> text pipeline) or "greeting" (bare wake).
    hold_for_verdict: bool = False
    verdict_action: Optional[str] = None
    verdict_command: str = ""
    verdict_reason: str = ""
    speaker_id: Optional[str] = None        # STT worker's speaker identification (thread-safe copy)
    speaker_confidence: float = 0.0
    speaker_resolved: bool = False
    superseded: bool = False        # request cancelled on purpose (text path took over)
    verdict_event: threading.Event = field(default_factory=threading.Event)
    _verdict_timer: Any = field(default=None, repr=False)
    _verdict_lock: Any = field(default_factory=threading.Lock, repr=False)


class DirectAudioService:
    """Creates and tracks direct-audio turns; owns no Coordinator state."""

    def __init__(self, llm, config, *,
                 context_provider: Optional[Callable[[AudioTurn], dict]] = None,
                 text_fallback_available: Optional[Callable[[], bool]] = None,
                 content_allowed: Optional[Callable[[], bool]] = None,
                 sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic,
                 poll_interval: float = 0.5):
        self.llm = llm
        self.config = config
        self._context_provider = context_provider
        self._fallback = text_fallback_available or (lambda: False)
        self._content_allowed = content_allowed or (lambda: True)
        self._sleep = sleep
        self._monotonic = monotonic
        self._poll_interval = poll_interval
        self._ids = itertools.count(1)
        self._turns: dict[str, AudioTurn] = {}
        self._active: dict[str, AudioTurn] = {}    # popped, being consumed right now
        self._lock = threading.Lock()
        self.status = "IDLE"        # last observed primary state: READY/STARTING/DOWN/IDLE

    # ----- configuration ----------------------------------------------------

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("llm.primary.audio_direct", False))

    @property
    def wake_compat(self) -> bool:
        value = self.config.get("stt.wake_compat", True)
        return True if value is None else bool(value)

    @property
    def verdict_timeout_s(self) -> float:
        """Max time an ungated direct answer is held for the STT verdict (0 = off)."""
        value = self.config.get("llm.primary.stt_verdict_timeout_s", 3.0)
        try:
            return max(0.0, float(3.0 if value is None else value))
        except (TypeError, ValueError):
            return 3.0

    @property
    def ready_wait_s(self) -> float:
        return float(self.config.get("llm.primary.ready_wait_s", 45) or 0)

    # ----- turn lifecycle -----------------------------------------------------

    def start_turn(self, audio, generation=None, in_conversation: bool = False,
                   ) -> Optional[AudioTurn]:
        """Start a direct-audio turn NOW (non-blocking; does not wait for STT).

        Returns None when direct audio is disabled or when the primary is not
        READY and a real text fallback exists (caller uses the text path).
        """
        if not self.enabled:
            return None
        state = self.llm.probe_role("primary")
        self.status = state
        if state == "READY":
            mode = "direct"
        elif self._fallback():
            return None
        else:
            mode = "wait"
        gate_required = self.wake_compat and not in_conversation
        turn_id = f"a{next(self._ids)}"
        verdict_timeout = self.verdict_timeout_s
        hold = (not gate_required) and verdict_timeout > 0
        turn, handle = self._new_turn(gate_required or hold)   # hold == buffer until verdict
        at = AudioTurn(
            turn_id=turn_id,
            turn=turn,
            stream_handle=handle,
            hold_for_verdict=hold,
            mode=mode, gate_required=gate_required, in_conversation=in_conversation,
            generation=generation, audio=audio,
            placeholder=f"[Sprachnachricht {turn_id}]",
        )
        # Context is assembled synchronously (cheap, read-only for gated turns)
        # so the caller can build its RouteResult; the model request itself is
        # started right away and never waits for STT.
        if self._context_provider is not None:
            try:
                at.context = self._context_provider(at) or {}
            except Exception:
                at.context = {}
        with self._lock:
            self._turns[turn_id] = at
        at.turn.begin(self._source(at))
        if hold:
            # No STT verdict in time -> release the direct answer (never blocks
            # the primary model on the parallel STT helper).
            timer = threading.Timer(verdict_timeout, self.set_verdict,
                                    args=(at, "direct", "", "stt_timeout"))
            timer.daemon = True
            at._verdict_timer = timer
            timer.start()
        return at

    def _new_turn(self, gate_required: bool):
        """SpeculativeTurn with a per-stream cancel handle when the LLM supports it,
        so cancelling this turn never closes another turn's stream."""
        handle = None
        factory = getattr(self.llm, "create_stream_handle", None)
        if callable(factory):
            try:
                handle = factory()
            except Exception:
                handle = None
        cancel = getattr(self.llm, "cancel_active_stream", None)
        if handle is not None and callable(cancel):
            cb = lambda h=handle: cancel(h)          # noqa: E731
        else:
            cb = cancel
        return SpeculativeTurn(gate_required=gate_required, cancel_cb=cb), handle

    def set_verdict(self, at: AudioTurn, action: str, command: str = "",
                    reason: str = "") -> bool:
        """Apply the (first) verdict of a held ungated turn.

        "direct"           -> release the buffered answer.
        "text"/"greeting"  -> cancel the model request, discard its buffer; the
                              consumer (_handle_command) switches to the text path.
        "reject"            -> cancel, no answer at all (noise/blank/stale/stop).
        Returns True only for the call that decided (first verdict wins).
        """
        if at is None or not at.hold_for_verdict:
            return False
        with at._verdict_lock:
            if at.verdict_action is not None:
                return False
            at.verdict_action = action
            at.verdict_command = command
            at.verdict_reason = reason
        timer = at._verdict_timer
        if timer is not None:
            timer.cancel()
        if action == "direct":
            at.turn.confirm_wake()
        elif action == "reject":
            at.turn.cancel()
        else:
            at.superseded = True
            at.turn.cancel()
        at.verdict_event.set()      # set AFTER the cancel: text path starts a fresh stream
        return True

    def _source(self, at: AudioTurn):
        if at.mode == "wait":
            self.status = "STARTING"
            deadline = self._monotonic() + self.ready_wait_s
            while True:
                if at.turn.is_rejected:
                    return
                state = self.llm.probe_role("primary", ttl=0.0)
                self.status = state
                if state == "READY":
                    break
                if self._monotonic() >= deadline:
                    at.failure = "primary_unavailable"
                    at.audio = None
                    return
                self._sleep(self._poll_interval)
        audio_b64 = self.llm.encode_audio_wav_b64(at.audio)
        at.audio = None                     # raw samples are not kept
        at.audio_b64 = audio_b64            # only for a context restart; cleared on finish
        yield from self._request(at, audio_b64)

    def _request(self, at: AudioTurn, audio_b64: str):
        ctx = at.context or {}     # read AFTER audio_b64 was published (see restart_turn)
        kwargs = dict(
            user_message=AUDIO_TURN_PROMPT,
            conversation_history=ctx.get("history") or "",
            memory_context=ctx.get("memory_context"),
            conversation_messages=ctx.get("conversation_messages"),
            guest_mode=bool(ctx.get("guest_mode", False)),
            audio_data=audio_b64,
            role="primary",
        )
        if at.stream_handle is not None:
            kwargs["cancel_handle"] = at.stream_handle
        tools = ctx.get("tools")
        if tools and getattr(self.llm, "tool_calling", False):
            yield from self.llm.stream_with_tools(tools=tools, **kwargs)
        else:
            yield from self.llm.stream(**kwargs)

    def restart_turn(self, at: AudioTurn, context: Optional[dict]) -> bool:
        """Replace the request of a turn with one built from a corrected context
        (e.g. the speaker turned out to be another one than assumed at start).

        Returns True if a running request was cancelled and restarted; when the
        request has not been sent yet only the context is updated.
        """
        at.context = context or {}
        b64 = at.audio_b64
        if b64 is None:
            return False
        old = at.turn
        old.cancel()
        new, at.stream_handle = self._new_turn(False)
        at.turn = new
        new.begin(self._request(at, b64))
        return True

    # ----- registry / metadata --------------------------------------------------

    def get(self, turn_id) -> Optional[AudioTurn]:
        with self._lock:
            return self._turns.get(turn_id)

    def pop(self, turn_id, active: bool = False) -> Optional[AudioTurn]:
        """Remove a turn from the registry. ``active=True`` keeps it tracked as
        the running turn (so a privacy flush / stop still cancels its stream)
        until :meth:`finish` is called."""
        with self._lock:
            at = self._turns.pop(turn_id, None)
            if at is not None and active:
                self._active[turn_id] = at
        if at is not None and not active:
            self._stop_timer(at)
        return at

    def finish(self, at: Optional[AudioTurn]) -> None:
        """The consumer is done with a popped turn: drop tracking and timer."""
        if at is None:
            return
        with self._lock:
            self._active.pop(at.turn_id, None)
        at.audio_b64 = None
        self._stop_timer(at)

    @staticmethod
    def _stop_timer(at: AudioTurn) -> None:
        timer = at._verdict_timer
        if timer is not None:
            timer.cancel()

    def active_turns(self) -> list:
        with self._lock:
            return list(self._active.values())

    def cancel_turn(self, turn_id) -> bool:
        """Cancel one turn (registered or currently consumed), any gate."""
        with self._lock:
            at = self._turns.pop(turn_id, None) or self._active.get(turn_id)
        if at is None:
            return False
        at.audio = None
        at.audio_b64 = None
        at.asr_hint = None
        self._stop_timer(at)
        at.turn.cancel()
        at.verdict_event.set()
        return True

    def note_transcript(self, turn_id, text: Optional[str]) -> None:
        """Attach the parallel ASR result as metadata. Never touches the model
        request and is dropped entirely when content logging is not allowed."""
        with self._lock:
            at = self._turns.get(turn_id) or self._active.get(turn_id)
        if at is None or not text:
            return
        at.asr_hint = text if self._content_allowed() else None

    def discard_all(self) -> int:
        """Privacy flush: cancel every open turn, drop audio and hints."""
        with self._lock:
            turns = list(self._turns.values()) + list(self._active.values())
            self._turns.clear()
            self._active.clear()
        for at in turns:
            at.audio = None
            at.audio_b64 = None
            at.asr_hint = None
            if at._verdict_timer is not None:
                at._verdict_timer.cancel()
            at.turn.cancel()
            at.verdict_event.set()
        return len(turns)


def store_user_turn(conversation, at: AudioTurn, speaker_confidence=None,
                    client_id: str = "voice") -> None:
    """Store the processed user turn: audio turn id + placeholder as content;
    the ASR transcript as in-memory ``asr_hint`` (LLM history context and memory
    hook when content logging is allowed; never written to disk, never the
    source of truth)."""
    try:
        conversation.add_message(
            "user", at.placeholder,
            speaker_confidence=speaker_confidence, client_id=client_id,
            asr_hint=at.asr_hint, audio_turn_id=at.turn_id,
        )
    except TypeError:       # conversation implementation without asr_hint support
        conversation.add_message(
            "user", at.placeholder,
            speaker_confidence=speaker_confidence, client_id=client_id,
        )
    history = getattr(conversation, "session_history", None)
    if history:
        message = history[-1]
        if isinstance(message, dict):
            message.setdefault("audio_turn_id", at.turn_id)
