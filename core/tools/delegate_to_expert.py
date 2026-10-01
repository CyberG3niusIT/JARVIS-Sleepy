"""Tool definition: delegate_to_expert — the Primary model hands ONE task to the Expert model.

Structured action instead of text magic. The Primary (Gemma) stays responsible for math,
coding, forensics and multi-step work; it calls this tool only when it truly cannot solve
the task itself. The handler builds an :class:`ExpertRequest` and passes it to a delegator
registered by the pipeline via :func:`set_expert_delegator` (the delegator runs
``core.model_handover.ModelHandover.run_expert``). Without a delegator the tool answers
honestly that the expert is unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Callable

TOOL_NAME = "delegate_to_expert"
ALWAYS_INCLUDED = True  # the model decides; there is no keyword gating

logger = logging.getLogger("jarvis.tools.delegate_to_expert")

SCHEMA = {
    "type": "function",
    "function": {
        "name": "delegate_to_expert",
        "description": (
            "Hand a single task to the slower, larger expert model. This costs a GPU model "
            "swap (many seconds during which the assistant is unavailable). Use it ONLY when "
            "you have honestly tried and truly cannot solve the task yourself, or the user "
            "explicitly asked for the expert."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why you cannot solve this yourself (one short sentence).",
                },
                "task": {
                    "type": "string",
                    "description": "Self-contained task for the expert, with all needed facts.",
                },
                "required_capability": {
                    "type": "string",
                    "description": "What the expert must be capable of, e.g. 'deep reasoning', 'long code analysis'.",
                },
                "original_user_intent": {
                    "type": "string",
                    "description": "The user's original request in their words (short).",
                },
                "needs_verification": {
                    "type": "boolean",
                    "description": "True if the expert's answer must be checked against hard constraints.",
                },
                "conversation_ref": {
                    "type": "string",
                    "description": "Conversation/turn id so the saved conversation state can be referenced.",
                },
            },
            "required": ["reason", "task"],
        },
    },
}

SYSTEM_PROMPT_RULE = (
    "Use delegate_to_expert ONLY when you truly cannot solve the task yourself after trying, "
    "or when the user explicitly asks for the expert (e.g. 'frag den Experten'). Math, coding, "
    "forensics and multi-step tasks are YOUR job: solve them yourself first. Never delegate "
    "just because a request is long or technical. Delegation swaps the GPU model and makes "
    "the assistant unavailable for a while."
)


@dataclass(frozen=True)
class ExpertRequest:
    reason: str
    task: str
    required_capability: str = ""
    original_user_intent: str = ""
    needs_verification: bool = False
    conversation_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


UNAVAILABLE_TEXT = "Der Experte ist derzeit nicht verfügbar."

# delegator(request) -> str | {"accepted": bool, "message": str} | None
_delegator: Callable[[ExpertRequest], Any] | None = None
_available: Callable[[], bool] | None = None


def set_expert_delegator(fn: Callable[[ExpertRequest], Any] | None,
                         available: Callable[[], bool] | None = None) -> None:
    """Register (or clear with None) the function that actually runs the handover."""
    global _delegator, _available
    _delegator, _available = fn, available


def is_available() -> bool:
    """Registry availability predicate: the tool (and its prompt rule) is only offered
    to the model while a delegator is registered and reports itself available
    (Coordinator.attach_handover clears it when handover.enabled is false)."""
    if _delegator is None:
        return False
    if _available is None:
        return True
    try:
        return bool(_available())
    except Exception:
        return False


def get_expert_delegator() -> Callable[[ExpertRequest], Any] | None:
    return _delegator


def build_request(args: dict) -> ExpertRequest | None:
    task = str(args.get("task") or "").strip()
    reason = str(args.get("reason") or "").strip()
    if not task or not reason:
        return None
    return ExpertRequest(
        reason=reason,
        task=task,
        required_capability=str(args.get("required_capability") or "").strip(),
        original_user_intent=str(args.get("original_user_intent") or "").strip(),
        needs_verification=bool(args.get("needs_verification", False)),
        conversation_ref=str(args.get("conversation_ref") or "").strip(),
    )


def handler(args: dict) -> str:
    request = build_request(args or {})
    if request is None:
        return "Fehler: 'reason' und 'task' sind erforderlich"
    if _delegator is None:
        return UNAVAILABLE_TEXT
    try:
        if _available is not None and not _available():
            return UNAVAILABLE_TEXT
        result = _delegator(request)
    except Exception as exc:  # honest failure, never a fake answer
        logger.warning("Expert delegation failed: %s", type(exc).__name__)
        return f"{UNAVAILABLE_TEXT} ({type(exc).__name__})"
    if isinstance(result, dict):
        message = str(result.get("message") or "")
        if result.get("accepted") is False:
            return message or UNAVAILABLE_TEXT
        return message or "Der Experte wurde eingeschaltet."
    return str(result) if result else "Der Experte wurde eingeschaltet."
