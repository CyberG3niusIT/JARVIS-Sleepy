"""Voice greeting uses the identified profile or the neutral guest path."""

from types import SimpleNamespace
import threading

import pytest

from core import persona
from core.honorific import clear_thread_user, get_honorific, set_honorific
from core.pipeline import Coordinator


class _Logger:
    def info(self, *args, **kwargs):
        pass


class _Profiles:
    def get_honorific_for(self, user_id):
        assert user_id == "primary_user"
        return "sir"

    def get_formal_address_for(self, user_id):
        return None


@pytest.fixture(autouse=True)
def _reset_honorific():
    clear_thread_user()
    set_honorific("sir")
    yield
    clear_thread_user()
    set_honorific("sir")


def _coordinator():
    spoken = []
    messages = []
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.logger = _Logger()
    coordinator.config = SimpleNamespace(get=lambda key, default=None: {
        "user_profiles.primary_user_id": "primary_user",
    }.get(key, default))
    coordinator.profile_manager = _Profiles()
    coordinator.conversation = SimpleNamespace(
        current_user=None,
        add_message=lambda *args, **kwargs: messages.append(args),
    )
    coordinator.context_window = None
    coordinator.reminder_manager = None
    coordinator.listener = SimpleNamespace(
        _extended_duration=12,
        open_conversation_window=lambda duration: None,
        resume_listening=lambda: None,
    )
    coordinator._speak_and_wait = spoken.append
    coordinator._turn_cancelled = threading.Event()
    coordinator._last_speaker_id = None
    coordinator._last_switch_time = 0.0
    coordinator._rapid_switch_count = 0
    return coordinator, spoken


def test_identified_primary_user_keeps_configured_sir(monkeypatch):
    coordinator, spoken = _coordinator()
    monkeypatch.setattr(persona.random, "choice", lambda pool: next(
        (item for item in pool if item == "Bereit, {h}."), pool[0]
    ))

    coordinator._apply_speaker_context("primary_user", 0.93)
    coordinator._handle_minimal_greeting("jarvis_only", False)

    assert coordinator.conversation.current_user == "primary_user"
    assert get_honorific() == "sir"
    assert spoken == ["Bereit, Sir."]


def test_unknown_voice_uses_neutral_german_guest_greeting(monkeypatch):
    coordinator, spoken = _coordinator()
    monkeypatch.setattr(persona.random, "choice", lambda pool: pool[0])

    coordinator._apply_speaker_context(None, 0.0)
    coordinator._handle_minimal_greeting("jarvis_only", False)

    assert coordinator.conversation.current_user == "__guest__"
    assert get_honorific() == "Gast"
    assert len(spoken) == 1
    assert "Ich erkenne Ihre Stimme nicht" in spoken[0]
    assert "friend" not in spoken[0].lower()
    assert "friend" not in persona.system_prompt_guest().lower()


def test_guest_greeting_does_not_clear_or_speak_pending_owner_rundown(monkeypatch):
    monkeypatch.setattr(persona, "guest_greeting", lambda: "Neutrale Begrüßung.")
    coordinator, spoken = _coordinator()
    cleared = []
    coordinator.reminder_manager = SimpleNamespace(
        has_rundown_mention=lambda: True,
        clear_rundown_mention=lambda: cleared.append(True),
    )
    coordinator.conversation.current_user = "__guest__"

    coordinator._handle_minimal_greeting("jarvis_only", False)

    assert spoken == ["Neutrale Begrüßung."]
    assert cleared == []


def test_unidentified_voice_clears_previous_primary_identity():
    coordinator, _ = _coordinator()
    coordinator.conversation.current_user = "primary_user"

    coordinator._apply_speaker_context(None, 0.0)

    assert coordinator.conversation.current_user == "__guest__"
    assert get_honorific() == "Gast"
