"""SpeculativeTurn - side-effect-free speculative LLM turn (wake gate).

Direct-audio turns start the primary-LLM request immediately, before the
parallel STT wake check has finished. Outside an active conversation window
that request is *speculative*: until the wake word is confirmed it must have
NO externally visible effect:

  * no tool execution
  * no memory write
  * no ConversationState mutation / persisted user history
  * no TTS, no UI publish

The class enforces this structurally. A producer thread only *buffers* the
items (text tokens and ToolCallRequest objects) coming out of the LLM stream.
All downstream effects live in the consumer that iterates :meth:`stream`; that
generator yields nothing until :meth:`confirm_wake` was called, so tools, state,
history, TTS and UI (which are driven by consumed items) cannot run early.

    turn = SpeculativeTurn(gate_required=True, cancel_cb=llm.cancel_active_stream)
    turn.begin(llm_stream_iterable)      # request starts now, buffered only
    ...
    turn.confirm_wake()                  # -> buffer released exactly once
    turn.reject()                        # -> stream cancelled, buffer discarded

Inside a conversation window (``gate_required=False``) there is no gate: the
turn is confirmed from the start.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable, Iterable, Iterator, Optional

_log = logging.getLogger("jarvis.speculative_turn")

PENDING = "pending"
CONFIRMED = "confirmed"
REJECTED = "rejected"


class SpeculativeTurn:
    """Buffers an LLM stream until the wake word is confirmed or rejected."""

    def __init__(self, gate_required: bool = True,
                 cancel_cb: Optional[Callable[[], None]] = None,
                 on_release: Optional[Callable[[list], None]] = None):
        self.gate_required = bool(gate_required)
        self._cancel_cb = cancel_cb
        self._on_release = on_release
        self._cond = threading.Condition()
        self._items: deque = deque()
        self._state = PENDING if self.gate_required else CONFIRMED
        self._producer_done = False
        self._release_called = False
        self._cancel_called = False
        self._thread: Optional[threading.Thread] = None
        self._source: Any = None
        self.error: Optional[BaseException] = None
        self.created_at = time.monotonic()
        self.item_count = 0            # total items produced (diagnostics only)

    # ----- state ---------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_confirmed(self) -> bool:
        return self._state == CONFIRMED

    @property
    def is_rejected(self) -> bool:
        return self._state == REJECTED

    @property
    def effects_allowed(self) -> bool:
        """True once (and only once) externally visible effects may run."""
        return self._state == CONFIRMED

    @property
    def buffered_tokens(self) -> list:
        """Text tokens currently held back (empty after reject)."""
        with self._cond:
            return [item for item in self._items if isinstance(item, str)]

    @property
    def buffered_items(self) -> list:
        with self._cond:
            return list(self._items)

    # ----- producer --------------------------------------------------------

    def begin(self, source: Iterable) -> None:
        """Start consuming `source` (the LLM stream) into the buffer.

        Returns immediately. The producer never triggers an effect; it only
        appends to the buffer and stops early when the turn is rejected.
        """
        with self._cond:
            if self._thread is not None:
                raise RuntimeError("SpeculativeTurn.begin() called twice")
            self._source = source
            self._thread = threading.Thread(
                target=self._produce, args=(source,),
                name="speculative-turn", daemon=True,
            )
        self._thread.start()
        # No gate: effects are allowed from the start (release exactly once).
        if not self.gate_required:
            self._release_once()

    def _produce(self, source: Iterable) -> None:
        iterator = iter(source)
        try:
            for item in iterator:
                with self._cond:
                    if self._state == REJECTED:
                        break
                    self._items.append(item)
                    self.item_count += 1
                    self._cond.notify_all()
        except BaseException as exc:  # noqa: BLE001 - reported via .error
            self.error = exc
            # Type only: never log content (privacy).
            _log.warning("Speculative producer failed (%s)", type(exc).__name__)
        finally:
            close = getattr(iterator, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
            with self._cond:
                self._producer_done = True
                self._cond.notify_all()

    # ----- decision ----------------------------------------------------------

    def confirm_wake(self) -> bool:
        """Wake confirmed: release the buffer. Returns True only for the call
        that actually performed the transition (exactly-once release)."""
        with self._cond:
            if self._state == REJECTED:
                return False
            transitioned = self._state == PENDING
            self._state = CONFIRMED
            self._cond.notify_all()
        self._release_once()
        return transitioned

    def reject(self) -> bool:
        """No wake: cancel the in-flight LLM request and discard the buffer.

        Returns True if this call rejected the turn; False if it was already
        confirmed (a released turn can no longer be rejected) or rejected.
        """
        with self._cond:
            if self._state != PENDING:
                return False
            self._state = REJECTED
            self._items.clear()
            self._cond.notify_all()
        self._cancel_once()
        return True

    def _release_once(self) -> None:
        with self._cond:
            if self._release_called:
                return
            self._release_called = True
            snapshot = list(self._items)
        if self._on_release is not None:
            self._on_release(snapshot)

    def _cancel_once(self) -> None:
        with self._cond:
            if self._cancel_called:
                return
            self._cancel_called = True
        if self._cancel_cb is not None:
            try:
                self._cancel_cb()
            except Exception:
                pass

    @property
    def release_count(self) -> int:
        return 1 if self._release_called else 0

    # ----- consumer ----------------------------------------------------------

    def stream(self, decision_timeout: Optional[float] = None) -> Iterator:
        """Yield buffered + live items once the turn is confirmed.

        Blocks while PENDING. If `decision_timeout` elapses without a wake
        decision the turn is rejected (no wake evidence -> no output). Yields
        nothing for a rejected turn.
        """
        deadline = None if decision_timeout is None else time.monotonic() + decision_timeout
        with self._cond:
            while self._state == PENDING:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    break
                self._cond.wait(timeout=remaining if remaining is not None else 0.25)
            timed_out = self._state == PENDING
        if timed_out:
            self.reject()
            return
        while True:
            with self._cond:
                while not self._items and not self._producer_done and self._state == CONFIRMED:
                    self._cond.wait(timeout=0.25)
                if self._state == REJECTED:
                    return
                if self._items:
                    item = self._items.popleft()
                elif self._producer_done:
                    return
                else:
                    continue
            yield item

    def cancel(self) -> None:
        """Abort an already-confirmed turn (barge-in / privacy flush)."""
        with self._cond:
            was_pending_or_confirmed = self._state != REJECTED
            self._state = REJECTED
            self._items.clear()
            self._cond.notify_all()
        if was_pending_or_confirmed:
            self._cancel_once()

    def join(self, timeout: Optional[float] = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)
