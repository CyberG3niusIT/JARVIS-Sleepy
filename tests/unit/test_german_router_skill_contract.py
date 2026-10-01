"""Owner replies stay German while external data and authorization stay intact."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.conversation_router import ConversationRouter
from core.reminder_manager import ReminderManager
from core.tools import manage_reminders
from skills.system.developer_tools.skill import DeveloperToolsSkill


def test_english_self_identification_has_german_owner_reply():
    router = ConversationRouter.__new__(ConversationRouter)
    router.conversation = SimpleNamespace(current_user="synthetic-user")
    router.memory_manager = Mock()
    result = router._handle_self_identification("my name is Ada")
    assert result.handled and result.intent == "self_identification"
    assert "Ich merke mir das" in result.text
    assert "Ada" in result.text
    assert router.memory_manager.store_fact.call_args.args[0]["user_id"] == "synthetic-user"


@pytest.mark.parametrize("answer,executes", [("yes", True), ("no", False), ("yesterday", False)])
def test_destructive_skill_german_preview_preserves_english_confirmation(answer, executes):
    skill = DeveloperToolsSkill.__new__(DeveloperToolsSkill)
    skill._honorific = "sir"
    skill.conversation = SimpleNamespace(request_follow_up=None)
    skill._llm = Mock()
    skill._llm.generate.return_value = "rm /tmp/synthetic-german-test.txt"
    skill._run_command = Mock(return_value=(True, ""))
    skill._summarize_for_voice = Mock(return_value="Erledigt.")
    skill._respond_with_output = Mock(return_value="Erledigt.")
    preview = skill.file_delete({"original_text": "delete the synthetic file"})
    assert "Dabei werden Dateien gelöscht" in preview
    assert "Soll ich fortfahren?" in preview
    skill._run_command.assert_not_called()
    skill.confirm_action({"original_text": answer})
    assert skill._run_command.called is executes


def test_unavailable_desktop_handler_is_german_and_does_not_execute():
    from skills.system.app_launcher.skill import AppLauncherSkill

    skill = AppLauncherSkill.__new__(AppLauncherSkill)
    skill._honorific = "sir"
    skill._desktop = None
    assert "nicht verfügbar" in skill.volume_up({})


def test_reminder_rundown_has_german_time_and_preserves_quoted_title():
    result = ReminderManager._format_items_naturally(
        [
            {"time": datetime(2026, 10, 1, 17), "title": "English Source Title"},
            {"time": datetime(2026, 10, 1, 18, 15), "title": "synthetic"},
        ]
    )
    assert "17:00 Uhr" in result and "danach" in result
    assert "English Source Title" in result
    assert "you have" not in result and " PM" not in result


def test_reminder_tool_missing_system_is_german(monkeypatch):
    monkeypatch.setattr(manage_reminders, "_reminder_manager", None)
    assert "nicht initialisiert" in manage_reminders.handler({"action": "add"})


def test_owner_language_rule_in_developer_summary_keeps_source_data():
    from core.persona import OWNER_LANGUAGE_RULE
    from skills.system.developer_tools._prompts import summarize_output_prompt

    prompt = summarize_output_prompt("synthetic_command", "English Source Title", "summarize")
    assert OWNER_LANGUAGE_RULE in prompt
    assert "English Source Title" in prompt and "synthetic_command" in prompt


def test_skill_execution_exception_is_german_and_audited():
    from core.skill_manager import SkillManager

    manager = SkillManager.__new__(SkillManager)
    manager._check_pending_confirmations = Mock(return_value=None)
    manager.match_intent = Mock(return_value=("synthetic", "action", {}))
    manager.skills = {"synthetic": SimpleNamespace(handle_intent=Mock(side_effect=RuntimeError("synthetic failure")))}
    manager.logger = Mock()
    manager._emit_skill_audit_event = Mock()
    reply = manager.execute_intent("synthetic request")
    assert "Fehler" in reply and "Verarbeitung" in reply
    assert isinstance(manager._emit_skill_audit_event.call_args.kwargs["error"], RuntimeError)


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("priority", [1, 2])
def test_proactive_news_owner_frame_is_german_with_original_source(index, priority, monkeypatch):
    import random
    import threading
    from core.news_manager import NewsManager

    manager = NewsManager.__new__(NewsManager)
    manager._pending_lock = threading.Lock()
    manager._pending_announcements = [
        {
            "id": 1,
            "priority": priority,
            "category": "tech",
            "source": "Synthetic API",
            "headline": "English Source Title",
        }
    ]
    manager._pause_listener_callback = None
    manager._resume_listener_callback = None
    manager._open_window_callback = None
    manager.tts = Mock()
    manager.mark_read = Mock()
    manager.mark_announced = Mock()
    monkeypatch.setattr(random, "choice", lambda choices: choices[index])
    manager.announce_pending()
    spoken = manager.tts.speak.call_args.args[0]
    assert "English Source Title" in spoken and "Synthetic API" in spoken
    assert any(word in spoken for word in ("Meldung", "meldet", "berichtet", "Beachtenswert"))
    assert "I have" not in spoken and "urgent" not in spoken
