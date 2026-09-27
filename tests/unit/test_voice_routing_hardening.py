"""Regressions for voice command normalization and identity routing."""

import queue
import threading
import logging
from types import SimpleNamespace

import pytest

from core.events import EventType
from core.pipeline import Coordinator
from core.wake_word_utils import strip_wake_word


@pytest.mark.parametrize(("text", "expected"), [
    ("Aura, mach mir einen Screenshot.", "mach mir einen Screenshot"),
    ("Mach mir einen Screenshot, Aura.", "Mach mir einen Screenshot"),
    ("Kannst du mir bitte, Aura, einen Screenshot machen?",
     "Kannst du mir bitte einen Screenshot machen"),
])
def test_wake_word_is_removed_at_any_sentence_position(text, expected):
    assert strip_wake_word(text, "aura") == expected


def test_german_screenshot_request_forces_existing_local_tool(monkeypatch):
    from core.conversation_router import ConversationRouter
    from core.tool_registry import TAKE_SCREENSHOT_TOOL

    router = ConversationRouter.__new__(ConversationRouter)
    router.conversation = SimpleNamespace(current_user="primary_user", client_type="desktop")
    router._select_tools_for_command = lambda command: None
    router._apply_anaphoric_carryover = lambda tools: tools
    router._prepare_llm_context = lambda command, **kwargs: SimpleNamespace(
        llm_command=command, llm_history="", context_messages=None,
        memory_context=None, force_web_search=False,
    )
    monkeypatch.setattr(
        "core.debug_logger.get_debug_logger",
        lambda: SimpleNamespace(_write=lambda *a, **k: None),
    )
    command = strip_wake_word("Mach mir bitte einen Screenshot, Aura.", "aura")
    result = router._handle_tool_calling(command)

    assert result is not None
    assert result.force_tool_call == "take_screenshot"
    assert result.use_tools == [TAKE_SCREENSHOT_TOOL]
    assert result.force_web_search is False


def test_negated_screenshot_does_not_trigger_capture(monkeypatch):
    from core.conversation_router import ConversationRouter

    router = ConversationRouter.__new__(ConversationRouter)
    router.conversation = SimpleNamespace(current_user="primary_user", client_type="desktop")
    router._select_tools_for_command = lambda command: None
    router._apply_anaphoric_carryover = lambda tools: tools
    assert router._handle_tool_calling("Mach mir bitte keinen Screenshot") is None


def test_forced_screenshot_uses_existing_tool_call_without_llm_selection(monkeypatch):
    from core.llm_router import LLMRouter, ToolCallRequest
    from core.tool_registry import TAKE_SCREENSHOT_TOOL

    llm = LLMRouter.__new__(LLMRouter)
    llm._stream_cancel_event = threading.Event()
    llm.reset_call_chain = lambda: None
    llm.tool_calling = True
    llm.temperature = 0.0
    llm.top_p = 1.0
    llm.top_k = 1
    llm.presence_penalty = 0.0
    llm._estimate_max_tokens = lambda command: 64
    llm._build_system_prompt = lambda **kwargs: "system"
    llm._build_user_message = lambda text, image_data=None: {
        "role": "user", "content": text,
    }
    llm.logger = logging.getLogger("test.forced_screenshot")
    monkeypatch.setattr(
        "core.debug_logger.get_debug_logger",
        lambda: SimpleNamespace(log_llm_messages=lambda *args, **kwargs: None),
    )

    yielded = list(llm.stream_with_tools(
        "Mach mir bitte einen Screenshot", tools=[TAKE_SCREENSHOT_TOOL],
        force_tool_call="take_screenshot",
    ))

    assert len(yielded) == 1
    assert isinstance(yielded[0], ToolCallRequest)
    assert yielded[0].name == "take_screenshot"
    assert yielded[0].arguments == {"action": "capture", "target": "monitor"}


def test_wake_word_stop_interrupt_is_terminal_and_not_queued():
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.listener = SimpleNamespace(
        _speaking_event=threading.Event(), active_tts_text="Lange Antwort",
        _capture_generation=1, invalidate_pending_audio=lambda: None,
    )
    coordinator.listener._speaking_event.set()
    coordinator.tts = SimpleNamespace(interrupt_active=lambda: None)
    coordinator.llm = SimpleNamespace(cancel_active_stream=lambda: None)
    coordinator.event_queue = queue.Queue()
    coordinator._turn_cancelled = threading.Event()
    coordinator._active_audio_pipeline = None
    coordinator._active_response_text = ""
    coordinator._barge_in_lock = threading.Lock()
    coordinator.wake_word = "aura"
    coordinator.logger = SimpleNamespace(info=lambda *a, **k: None)

    assert coordinator.handle_barge_in("Aura, stopp bitte")
    assert coordinator.event_queue.empty()


@pytest.mark.parametrize("speaker_id", [None, "__guest__"])
def test_single_user_mic_unknown_maps_to_configured_primary_without_verification(speaker_id):
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.logger = SimpleNamespace(info=lambda *a, **k: None)
    coordinator.config = SimpleNamespace(get=lambda key, default=None: {
        "user_profiles.primary_user_id": "primary_user",
        "user_profiles.single_user_mode": True,
    }.get(key, default))
    applied = []
    coordinator.profile_manager = SimpleNamespace(
        get_honorific_for=lambda user_id: "sir",
        get_formal_address_for=lambda user_id: None,
    )
    coordinator.conversation = SimpleNamespace(current_user=None)
    coordinator.context_window = SimpleNamespace(set_user=applied.append)
    coordinator._last_speaker_id = None
    coordinator._last_switch_time = 0.0
    coordinator._rapid_switch_count = 0

    coordinator._apply_speaker_context(speaker_id, 0.0)

    assert coordinator.conversation.current_user == "primary_user"
    assert applied == ["primary_user"]
    assert coordinator._last_speaker_confidence == 0.0
    assert coordinator._last_speaker_id == "primary_user"


def test_single_user_fallback_does_not_override_recognized_other_user():
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.logger = SimpleNamespace(info=lambda *a, **k: None)
    coordinator.config = SimpleNamespace(get=lambda key, default=None: {
        "user_profiles.primary_user_id": "primary_user",
        "user_profiles.single_user_mode": True,
    }.get(key, default))
    coordinator.profile_manager = SimpleNamespace(
        get_profile=lambda user_id: {"id": user_id},
        get_honorific_for=lambda user_id: "ma'am",
        get_formal_address_for=lambda user_id: "Ms. Guest",
    )
    coordinator.conversation = SimpleNamespace(current_user=None)
    applied = []
    coordinator.context_window = SimpleNamespace(set_user=applied.append)
    coordinator._last_speaker_id = None
    coordinator._last_switch_time = 0.0
    coordinator._rapid_switch_count = 0

    coordinator._apply_speaker_context("recognized_user", 0.91)

    assert coordinator.conversation.current_user == "recognized_user"
    assert applied == ["recognized_user"]
