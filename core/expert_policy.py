"""Expert escalation policy: when may the Primary (Gemma) hand a turn to the Expert (Qwen)?

BINDING RULES (plan "Schritt 3"):

* NO blanket domain rules. Math, coding, forensics and multi-step requests stay on the
  Primary. Nothing in here looks at topic keywords or request length.
* Escalation happens ONLY for one of three reasons:
    (a) an explicit expert request: a Primary tool call (``delegate_to_expert``) or an
        explicit user wish such as "frag den Experten";
    (b) a truly high complexity signal that the Primary itself reported as a structured
        value (never derived from keywords or text length here);
    (c) a failed *hard* verification (a callable returned False, e.g. a constraint check
        for a number puzzle) or an unreliable tool result.
* Long requests are never delegated automatically.

Stdlib only; pure functions, no I/O, no model calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable

# Reasons (stable identifiers for logs/tests)
REASON_NONE = "stay_primary"
REASON_EXPLICIT_TOOL = "explicit_tool_call"
REASON_EXPLICIT_USER = "explicit_user_request"
REASON_HIGH_COMPLEXITY = "primary_reported_high_complexity"
REASON_VERIFICATION_FAILED = "hard_verification_failed"
REASON_TOOL_UNRELIABLE = "tool_result_unreliable"

# Small, exact list of explicit wishes. Deliberately NOT a domain/keyword heuristic.
EXPLICIT_EXPERT_PHRASES: tuple[str, ...] = (
    "frag den experten",
    "frag mal den experten",
    "frage den experten",
    "hol den experten",
    "hole den experten",
    "hol dir den experten",
    "ruf den experten",
    "ruf den experten dazu",
    "lass den experten",
    "ask the expert",
    "call the expert",
    "get the expert",
)

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)

# Structured complexity levels a Primary signal may carry.
HIGH_COMPLEXITY_LEVELS = frozenset({"high", "very_high", "extreme"})


def _normalize(text: str) -> str:
    return _WS.sub(" ", _PUNCT.sub(" ", (text or "").lower())).strip()


_NEG_TAIL = frozenset({"nicht", "nie", "niemals", "ruhe", "not", "never", "dont", "kein", "keinen"})
_NEG_HEAD = frozenset({"nicht", "ohne", "kein", "keine", "keinen", "nie", "niemals",
                       "not", "never", "dont", "don", "without"})


def _negated(words: list[str], start: int, end: int) -> bool:
    """A phrase at words[start:end] is negated ('frag den Experten bitte nicht',
    'lass den Experten in Ruhe', 'nicht den Experten ...')."""
    tail = words[end:end + 4]
    head = words[max(0, start - 2):start]
    return any(w in _NEG_TAIL for w in tail) or any(w in _NEG_HEAD for w in head)


def is_explicit_expert_request(user_text: str) -> bool:
    """True only if the user literally asks for the expert (exact phrase list).

    Negated wishes ('frag den Experten bitte nicht', 'lass den Experten in Ruhe',
    'ohne Experten', 'kein Experte') never escalate."""
    words = _normalize(user_text).split()
    for phrase in EXPLICIT_EXPERT_PHRASES:
        pw = phrase.split()
        n = len(pw)
        for i in range(len(words) - n + 1):
            if words[i:i + n] == pw and not _negated(words, i, i + n):
                return True
    return False


@dataclass(frozen=True)
class EscalationDecision:
    escalate: bool
    reason: str = REASON_NONE
    detail: str = ""

    def __bool__(self) -> bool:  # allows ``if should_escalate(...)``
        return self.escalate


def _high_complexity(signal: Any) -> bool:
    """Structured signal only: {"complexity": "high"} / {"needs_expert": True} / "high"."""
    if signal is None:
        return False
    if isinstance(signal, str):
        return signal.strip().lower() in HIGH_COMPLEXITY_LEVELS
    if isinstance(signal, dict):
        if signal.get("needs_expert") is True:
            return True
        level = signal.get("complexity")
        return isinstance(level, str) and level.strip().lower() in HIGH_COMPLEXITY_LEVELS
    return False


def should_escalate(
    user_text: str = "",
    gemma_signal: Any = None,
    verification_result: bool | None = None,
    tool_result_reliable: bool | None = None,
    explicit_request: bool = False,
) -> EscalationDecision:
    """Decide whether this turn goes to the expert.

    Args:
        user_text: the user's words. Only checked against the exact explicit-wish phrases;
            never inspected for domain keywords or length.
        gemma_signal: structured complexity signal reported by the Primary
            (dict with ``complexity``/``needs_expert``, or a level string). None = none.
        verification_result: result of a hard verification. ``False`` = failed;
            ``True``/``None`` = passed or not run.
        tool_result_reliable: ``False`` = a tool result is known to be unreliable.
        explicit_request: True when the Primary called ``delegate_to_expert``.
    """
    if explicit_request:
        return EscalationDecision(True, REASON_EXPLICIT_TOOL, "Primary hat delegate_to_expert aufgerufen.")
    if is_explicit_expert_request(user_text):
        return EscalationDecision(True, REASON_EXPLICIT_USER, "Ausdruecklicher Nutzerwunsch nach dem Experten.")
    if _high_complexity(gemma_signal):
        return EscalationDecision(True, REASON_HIGH_COMPLEXITY, "Primary meldet hohe Komplexitaet.")
    if verification_result is False:
        return EscalationDecision(True, REASON_VERIFICATION_FAILED, "Harte Verifikation fehlgeschlagen.")
    if tool_result_reliable is False:
        return EscalationDecision(True, REASON_TOOL_UNRELIABLE, "Tool-Ergebnis ist nicht zuverlaessig.")
    return EscalationDecision(False)


def verify_constraints(
    answer: Any,
    constraints: Iterable[Callable[[Any], bool]],
) -> bool:
    """Hard verification hook: every callable constraint must hold for ``answer``.

    Returns False when any constraint is False or raises (an unverifiable answer is not
    a verified one). An empty constraint list returns True (nothing to fail).
    Feed the result into ``should_escalate(verification_result=...)``.
    """
    for check in constraints:
        try:
            if not check(answer):
                return False
        except Exception:
            return False
    return True
