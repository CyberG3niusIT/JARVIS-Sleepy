"""Real confirmation handlers with all destructive effects replaced by spies."""
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from skills.system.developer_tools.skill import DeveloperToolsSkill
from skills.system.file_editor.skill import FileEditorSkill


@pytest.fixture(params=["developer", "delete", "overwrite"])
def pending(request):
    effect = Mock()
    if request.param == "developer":
        skill = DeveloperToolsSkill.__new__(DeveloperToolsSkill)
        skill._pending_confirmation = ("rm isolated-placeholder", time.time() + 30)
        skill._run_command = Mock(side_effect=lambda *_: (effect(), "stub-output"))
        skill._summarize_for_voice = Mock(return_value="stub-summary")
        skill._respond_with_output = Mock(return_value="stub-response")
    else:
        skill = FileEditorSkill.__new__(FileEditorSkill)
        skill.logger = Mock()
        skill._pending_confirmation = (request.param, {
            "filename": "isolated-placeholder", "filetype": "txt",
            "description": "stub", "user_text": "stub",
        }, time.time() + 30)
        skill._safe_path = Mock(return_value=SimpleNamespace(exists=lambda: True, unlink=effect))
        skill._generate_and_save = Mock(side_effect=lambda *_: (effect(), "stub-response")[1])
    return skill, effect


@pytest.mark.parametrize("text", [
    "nein", "nein danke", "abbrechen", "stop", "stopp", "nicht machen",
    "nein, jarvis, abbrechen", "ja, aber nein", "ja, aber nein, abbrechen",
    "nein, doch nicht", "ja, nicht machen", "no", "no thanks", "cancel",
    "abort", "never mind", "don't", "yes, but no", "yes, do not do it",
    "vergiss es", "lass es", "nope", "nevermind", "yes, don't", "yes, don’t",
])
def test_denial_never_executes_and_clears_pending(pending, text):
    skill, effect = pending
    assert skill.confirm_action({"original_text": text})
    effect.assert_not_called()
    assert skill._pending_confirmation is None


@pytest.mark.parametrize("text", [
    "jahr", "januar", "javascript", "loslassen", "yesterday", "unknown", "",
    "ja vielleicht", "was bedeutet ja", "jarvis",
])
def test_unclear_text_never_executes_and_keeps_pending(pending, text):
    skill, effect = pending
    original = skill._pending_confirmation
    assert skill.confirm_action({"original_text": text})
    effect.assert_not_called()
    assert skill._pending_confirmation == original


@pytest.mark.parametrize("text", [
    "ja", "ja bitte", "bestätigen", "JA!", "ja, jarvis", "mach das",
    "weiter", "los", "bestätigt", "yes", "yes please", "go ahead",
    "proceed", "do it", "confirmed", "affirmative", "yes go ahead", "yeah do it",
    "jep", "klar", "sure", "tu es",
])
def test_explicit_acceptance_executes_exactly_once(pending, text):
    skill, effect = pending
    assert skill.confirm_action({"original_text": text})
    effect.assert_called_once()
    assert skill._pending_confirmation is None
    assert skill.confirm_action({"original_text": text}) is None
    effect.assert_called_once()


def test_expired_confirmation_never_executes(pending):
    skill, effect = pending
    skill._pending_confirmation = (*skill._pending_confirmation[:-1], time.time() - 1)
    assert skill.confirm_action({"original_text": "ja"})
    effect.assert_not_called()
    assert skill._pending_confirmation is None


@pytest.mark.parametrize("text", ["ja bitte", "nein, jarvis, abbrechen", "go ahead"])
def test_router_dispatches_pending_skill_confirmation_without_llm(text):
    from core.conversation_router import ConversationRouter
    skill = SimpleNamespace(_pending_confirmation=("delete", {}, time.time() + 30),
                            confirm_action=Mock(return_value="handled"))
    router = ConversationRouter.__new__(ConversationRouter)
    router.skill_manager = SimpleNamespace(skills={"file_editor": skill})
    result = router._handle_skill_pending_confirmation(text)
    assert result is not None and result.handled
    skill.confirm_action.assert_called_once_with({"original_text": text})
