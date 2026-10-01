"""Regression cases found by independent review; no runtime or external calls."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock
import sys

import pytest
from core import persona


@pytest.mark.parametrize("index,total", [(0, 1), (1, 3), (2, 3)])
def test_news_speech_templates_have_german_frames_and_preserve_source(monkeypatch, index, total):
    from core.news_manager import NewsManager

    choices = iter(range(6))
    monkeypatch.setattr("random.choice", lambda items: items[next(choices) % len(items)])
    monkeypatch.setattr("random.shuffle", lambda items: None)
    NewsManager._follow_queue.clear()
    outputs = [
        NewsManager._format_headline_for_speech("Reuters", "English source title", index, total) for _ in range(6)
    ]
    assert all("Reuters" in output and "English source title" in output for output in outputs)
    assert all("Separately" not in output and "Finally" not in output for output in outputs)
    assert all(
        any(word in output for word in ("berichtet", "meldet", "Bei", "Laut", "Von", "von")) for output in outputs
    )


def test_news_unread_count_has_german_frame():
    from core.news_manager import NewsManager

    manager = NewsManager.__new__(NewsManager)
    manager.get_unread_count = lambda **kwargs: {"technology": 2}
    response = manager.get_headline_count_response()
    assert response.startswith("Du hast 2 neue Schlagzeilen")
    assert response.endswith("Möchtest du sie hören?")


def test_previous_search_page_has_german_result_count():
    from threading import RLock
    from skills.system.web_navigation.skill import WebNavigationSkill

    skill = WebNavigationSkill.__new__(WebNavigationSkill)
    skill._scrape_lock = RLock()
    skill._last_search_type = "google"
    skill._last_query = "example"
    skill._current_page = 3
    skill._scroll_sites = {"google"}
    skill._current_page_results = lambda: ["Original result"]
    skill.conversation = SimpleNamespace()
    skill.follow_up_duration = 1
    skill.respond = lambda text: text
    assert "Seite 2, 1 Ergebnisse" in skill.previous_page()
    assert skill._current_page == 2


@pytest.mark.parametrize("provider", ["openrouter", "anthropic"])
def test_cloud_generate_real_provider_payload_has_owner_language_rule(monkeypatch, provider):
    from core.llm_router import LLMRouter

    values = {
        "llm.api.enabled": True,
        "llm.api.provider": provider,
        "llm.api.model": "synthetic-model",
        "llm.api.api_key_env": "OPENROUTER_API_KEY" if provider == "openrouter" else "ANTHROPIC_API_KEY",
        "llm.api.endpoint": "https://synthetic.invalid/api",
    }
    router = LLMRouter.__new__(LLMRouter)
    router.config = SimpleNamespace(
        get=lambda k, default=None: values.get(k, default), get_env=lambda k: "SYNTHETIC_FIXTURE_CREDENTIAL"
    )
    router.logger = Mock()
    router._record_call = Mock()
    router._privacy_gate = SimpleNamespace(allow=lambda cap: True)
    if provider == "openrouter":
        response = Mock()
        response.json.return_value = {"choices": [{"message": {"content": "Hallo."}}]}
        send = Mock(return_value=response)
        monkeypatch.setattr("core.llm_router.requests.post", send)
    else:
        send = Mock(
            return_value=SimpleNamespace(
                content=[SimpleNamespace(text="Hallo.")], usage=SimpleNamespace(input_tokens=1, output_tokens=1)
            )
        )
        client = SimpleNamespace(messages=SimpleNamespace(create=send))
        monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda **kw: client))
    assert router._generate_api("Antworte diesmal auf Englisch.") == "Hallo."
    payload = send.call_args.kwargs["json"] if provider == "openrouter" else send.call_args.kwargs
    system = payload["messages"][0]["content"] if provider == "openrouter" else payload["system"]
    assert persona.OWNER_LANGUAGE_RULE in system
    assert payload["messages"][-1]["content"] == "Antworte diesmal auf Englisch."
    assert send.call_count == 1


@pytest.mark.parametrize("failed_synthesis", [False, True])
def test_planner_fast_or_failed_synthesis_keeps_german_source_frame(failed_synthesis):
    from core.task_planner import TaskPlanner, TaskPlan, PlanStep, PlanStatus, StepStatus

    source = "I completed your task successfully."
    steps = [
        PlanStep(i, "Test", "synthetic", "input", status=StepStatus.COMPLETED, result=source)
        for i in range(2 if failed_synthesis else 1)
    ]
    plan = TaskPlan("Teste den Rahmen", steps, PlanStatus.COMPLETED)
    planner = TaskPlanner.__new__(TaskPlanner)
    planner._llm = Mock()
    planner._llm.chat.side_effect = TimeoutError("foreign failure")
    result = planner._synthesize_results(plan, [source for _ in steps])
    assert source in result
    assert result.startswith(
        "Ich konnte die Ergebnisse nicht zusammenfassen." if failed_synthesis else "Ergebnis des Werkzeugs:"
    )
    assert planner._llm.chat.call_count == int(failed_synthesis)


def test_file_read_has_german_header_and_preserves_foreign_file(tmp_path):
    from skills.system.file_editor.skill import FileEditorSkill

    path = tmp_path / "example.txt"
    path.write_text("English file contents", encoding="utf-8")
    skill = FileEditorSkill.__new__(FileEditorSkill)
    skill.logger = Mock()
    skill._resolve_read_path = Mock(return_value=path)
    result = skill.read_file({"original_text": "read example.txt"})
    assert result.startswith("Hier ist example.txt")
    assert result.endswith("English file contents")


@pytest.mark.parametrize(
    "text, rule, description",
    [
        ("every day at 8am to test", "daily:08:00", "jeden Tag um 08:00 Uhr"),
        ("every tuesday at 8am to test", "weekly:tue:08:00", "jeden Dienstag um 08:00 Uhr"),
    ],
)
def test_english_reminder_input_preserves_rule_with_german_description(text, rule, description):
    from skills.personal.reminders.skill import ReminderSkill

    skill = ReminderSkill.__new__(ReminderSkill)
    skill._manager_ref = SimpleNamespace(parse_natural_time=lambda text: datetime(2026, 10, 1, 8))
    result = skill._parse_recurring_command(text)
    assert result["rule"] == rule
    assert result["description"] == description
    assert result["title"] == "test"


def test_social_missing_relationship_is_german():
    from skills.personal.social_introductions.skill import SocialIntroductionsSkill

    skill = SocialIntroductionsSkill.__new__(SocialIntroductionsSkill)
    skill.conversation = SimpleNamespace(current_user="synthetic-user")
    skill._manager_ref = Mock()
    skill.manager.get_person_with_facts.return_value = {"name": "Ada", "facts": []}
    skill._extract_name_from_query = lambda text: "Ada"
    skill.respond = lambda text: text
    assert "Beziehung: eine bekannte Person" in skill.who_is()


def test_app_list_and_clipboard_truncation_have_german_frames():
    from skills.system.app_launcher.skill import AppLauncherSkill

    skill = AppLauncherSkill.__new__(AppLauncherSkill)
    skill._desktop = Mock()
    skill._desktop.list_windows.return_value = [{"wm_class": str(i), "title": f"App {i}"} for i in range(7)]
    assert "und 2 weitere" in skill.list_windows()
    skill._desktop.get_clipboard.return_value = "foreign content " * 20
    assert skill.read_clipboard().endswith("... und mehr")


@pytest.mark.parametrize("phrase", ["Ada ist derzeit 34 Jahre alt", "Ada is currently 34 years old"])
def test_age_consumers_preserve_computed_value_guard(monkeypatch, phrase):
    from core.memory_manager import MemoryManager
    from core.awareness import AwarenessAssembler

    monkeypatch.setattr("core.user_profile.get_profile_manager", lambda: None)
    fact = {"fact_id": "synthetic", "content": "date of birth", "score": 1.0, "times_referenced": 0}
    manager = MemoryManager.__new__(MemoryManager)
    manager.proactive_enabled = True
    manager.proactive_threshold = 0.5
    manager._surfaced_this_window = set()
    manager._search_facts_semantic = lambda *a, **kw: [fact]
    manager._fact_to_phrase = lambda f: phrase
    manager.update_fact = Mock()
    manager.logger = Mock()
    assert "do NOT calculate" in manager.get_proactive_context("age")
    assembler = AwarenessAssembler.__new__(AwarenessAssembler)
    assembler.memory_manager = manager
    assembler._fact_threshold = 0.5
    candidates = []
    assembler._gather_fact_candidates("age", "primary_user", candidates)
    assert "do NOT calculate" in candidates[0].text
