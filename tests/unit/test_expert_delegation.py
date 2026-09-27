"""Expert delegation: policy (no domain heuristics), tool schema/auto-discovery, honest unavailability."""

import pytest

from core import expert_policy as policy
from core.tools import delegate_to_expert as tool

STAY_ON_GEMMA = [
    "Berechne das Integral von x^2 * sin(x) von 0 bis pi und zeige jeden Schritt.",
    "Schreibe mir eine Python-Funktion, die einen Binaerbaum balanciert, mit Unit-Tests.",
    "Analysiere diese forensische Zeitleiste: Login 03:12, Dateizugriff 03:14, Export 03:15, Log geloescht 03:17. Was ist passiert?",
    "Erst die Wetterdaten holen, dann eine Route planen, dann eine Erinnerung setzen und alles zusammenfassen.",
    "x " * 2000,  # a very long request is never auto-delegated
]


@pytest.mark.parametrize("text", STAY_ON_GEMMA)
def test_math_coding_forensics_multistep_and_long_requests_stay_on_the_primary(text):
    decision = policy.should_escalate(text)
    assert decision.escalate is False and decision.reason == policy.REASON_NONE
    assert not decision  # falsy


@pytest.mark.parametrize("text", [
    "Frag den Experten, was davon stimmt.",
    "hol den Experten dazu!",
    "Kannst du bitte den Experten fragen? frag den experten",
    "ask the expert about this",
])
def test_explicit_user_wish_escalates(text):
    decision = policy.should_escalate(text)
    assert decision.escalate and decision.reason == policy.REASON_EXPLICIT_USER


def test_expert_word_alone_is_not_an_explicit_request():
    assert not policy.should_escalate("Er ist ein Experte fuer Mathe, erklaer mir Ableitungen.")


def test_gemma_tool_call_is_an_explicit_request():
    decision = policy.should_escalate("", explicit_request=True)
    assert decision.escalate and decision.reason == policy.REASON_EXPLICIT_TOOL


@pytest.mark.parametrize("signal", [{"complexity": "high"}, {"needs_expert": True}, "very_high"])
def test_structured_high_complexity_signal_escalates(signal):
    decision = policy.should_escalate("egal", gemma_signal=signal)
    assert decision.escalate and decision.reason == policy.REASON_HIGH_COMPLEXITY


@pytest.mark.parametrize("signal", [None, {"complexity": "low"}, {"complexity": "medium"}, {"needs_expert": False}, "hard"])
def test_other_signals_do_not_escalate(signal):
    assert not policy.should_escalate("egal", gemma_signal=signal)


def test_failed_hard_verification_escalates_and_passed_or_missing_does_not():
    assert policy.should_escalate("Loese das Zahlenraetsel", verification_result=False).reason == policy.REASON_VERIFICATION_FAILED
    assert not policy.should_escalate("Loese das Zahlenraetsel", verification_result=True)
    assert not policy.should_escalate("Loese das Zahlenraetsel", verification_result=None)


def test_unreliable_tool_result_escalates():
    decision = policy.should_escalate("x", tool_result_reliable=False)
    assert decision.escalate and decision.reason == policy.REASON_TOOL_UNRELIABLE
    assert not policy.should_escalate("x", tool_result_reliable=True)


def test_verify_constraints_hook():
    is_even = lambda n: n % 2 == 0
    positive = lambda n: n > 0
    assert policy.verify_constraints(4, [is_even, positive]) is True
    assert policy.verify_constraints(3, [is_even, positive]) is False
    assert policy.verify_constraints(3, []) is True
    assert policy.verify_constraints("x", [is_even]) is False       # a raising check is not "verified"
    # end to end: failed verification -> escalation
    assert policy.should_escalate("puzzle", verification_result=policy.verify_constraints(3, [is_even])).escalate


# -- tool -----------------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_delegator():
    tool.set_expert_delegator(None)
    yield
    tool.set_expert_delegator(None)


def test_schema_is_valid_and_complete():
    fn = tool.SCHEMA["function"]
    assert tool.SCHEMA["type"] == "function" and fn["name"] == tool.TOOL_NAME == "delegate_to_expert"
    props = fn["parameters"]["properties"]
    assert set(props) == {"reason", "task", "required_capability", "original_user_intent",
                          "needs_verification", "conversation_ref"}
    assert props["needs_verification"]["type"] == "boolean"
    assert set(fn["parameters"]["required"]) <= set(props)
    assert "truly cannot" in tool.SYSTEM_PROMPT_RULE and "solve" in tool.SYSTEM_PROMPT_RULE


def test_tool_registry_discovers_the_tool():
    from core import tool_registry
    assert "delegate_to_expert" in tool_registry.ALL_TOOLS
    assert tool_registry.ALL_TOOLS["delegate_to_expert"] is tool.SCHEMA
    assert "delegate_to_expert" in tool_registry.TOOL_HANDLERS


def test_handler_builds_a_structured_request_for_the_delegator():
    received = []
    tool.set_expert_delegator(lambda req: received.append(req) or "Ich hole den Experten.")
    text = tool.handler({
        "reason": "Beweis zu lang", "task": "Beweise X", "required_capability": "deep reasoning",
        "original_user_intent": "Beweis bitte", "needs_verification": True, "conversation_ref": "turn-7",
    })
    assert text == "Ich hole den Experten."
    request = received[0]
    assert isinstance(request, tool.ExpertRequest)
    assert request.to_dict() == {
        "reason": "Beweis zu lang", "task": "Beweise X", "required_capability": "deep reasoning",
        "original_user_intent": "Beweis bitte", "needs_verification": True, "conversation_ref": "turn-7",
    }


def test_handler_reports_unavailable_honestly_without_delegator():
    assert tool.handler({"reason": "r", "task": "t"}) == tool.UNAVAILABLE_TEXT


def test_handler_reports_unavailable_when_handover_is_not_available_or_fails():
    called = []
    tool.set_expert_delegator(lambda req: called.append(req), available=lambda: False)
    assert tool.handler({"reason": "r", "task": "t"}) == tool.UNAVAILABLE_TEXT
    assert called == []                                # never fakes an answer, never calls a dead delegator

    def broken(req):
        raise RuntimeError("no gpu")

    tool.set_expert_delegator(broken)
    assert tool.handler({"reason": "r", "task": "t"}).startswith(tool.UNAVAILABLE_TEXT)
    tool.set_expert_delegator(lambda req: {"accepted": False, "message": "Handover laeuft bereits."})
    assert tool.handler({"reason": "r", "task": "t"}) == "Handover laeuft bereits."


def test_handler_rejects_missing_task_or_reason():
    tool.set_expert_delegator(lambda req: "x")
    assert tool.handler({"task": "t"}).startswith("Error")
    assert tool.handler({"reason": "r"}).startswith("Error")


def test_router_route_result_defaults_and_explicit_hook():
    from core.conversation_router import ConversationRouter, RouteResult
    default = RouteResult()
    assert default.model_role == "primary" and default.expert_requested is False

    unhandled = RouteResult(handled=False)
    ConversationRouter._apply_expert_policy(unhandled, "Frag den Experten bitte")
    assert unhandled.model_role == "expert" and unhandled.expert_requested

    for text in STAY_ON_GEMMA[:4]:
        other = RouteResult(handled=False)
        ConversationRouter._apply_expert_policy(other, text)
        assert other.model_role == "primary" and not other.expert_requested

    handled = RouteResult(handled=True)
    ConversationRouter._apply_expert_policy(handled, "Frag den Experten")
    assert handled.model_role == "primary"
