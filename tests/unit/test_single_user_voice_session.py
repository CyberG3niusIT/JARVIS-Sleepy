"""Session and interrupt rules with synthetic audio and no microphone access."""

import queue
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from core.events import EventType
from core.honorific import clear_thread_user, get_honorific, set_honorific
from core.pipeline import Coordinator, STTWorker
from core.conversation_router import ConversationRouter
from core.llm_router import ToolCallRequest


class _Logger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _STT:
    def __init__(self):
        self.users = []

    def transcribe(self, audio, sample_rate, speaker_user_id=None):
        self.users.append(speaker_user_id)
        return "Stopp" if audio[0] == 9 else "Aura, wie spät ist es?"


class _Speaker:
    similarity_threshold = 0.30

    def __init__(self, results):
        self.results = iter(results)
        self.calls = 0

    def identify(self, audio, sample_rate):
        self.calls += 1
        return next(self.results)


def _worker(results, markers):
    events = queue.Queue()
    captures = queue.Queue()
    for marker in markers:
        captures.put({"audio": np.array([marker], dtype=np.float32),
                      "capture_generation": 1, "during_tts": marker == 9})
    captures.put(None)
    stt = _STT()
    speaker = _Speaker(results)
    listener = SimpleNamespace(_capture_generation=1)
    worker = STTWorker(stt, events, captures, speaker_id=speaker, listener=listener)
    return worker, speaker, stt, events


def test_bounded_session_tolerates_modest_variation_then_rejects_bad_match():
    worker, speaker, stt, events = _worker(
        [("primary_user", 0.90), (None, 0.285), (None, 0.10)], [1, 2, 3]
    )

    worker.run()

    identified = [events.get_nowait().data["speaker_id"] for _ in range(3)]
    assert identified == ["primary_user", "primary_user", None]
    assert stt.users == identified
    assert speaker.calls == 3


def test_session_identity_does_not_stick_through_repeated_borderline_samples():
    worker, speaker, _, events = _worker(
        [("primary_user", 0.90)] + [(None, 0.285)] * 3, [1, 2, 3, 4]
    )

    worker.run()

    identified = [events.get_nowait().data["speaker_id"] for _ in range(4)]
    assert identified == ["primary_user", "primary_user", "primary_user", None]
    assert speaker.calls == 4


@pytest.mark.parametrize("word", ["Stopp", "Stop", "Halt"])
def test_bare_stop_bypasses_speaker_identification_during_tts(word):
    worker, speaker, stt, events = _worker([], [9])
    stt.transcribe = lambda audio, sample_rate, speaker_user_id=None: word
    accepted = []
    worker.on_barge_in = lambda text, user_id, confidence: accepted.append(
        (text, user_id, confidence)
    ) or True

    worker.run()

    assert accepted == [(word, None, 0.0)]
    assert speaker.calls == 0
    assert events.empty()


@pytest.fixture(autouse=True)
def _clean_honorific():
    clear_thread_user()
    set_honorific("sir")
    yield
    clear_thread_user()
    set_honorific("sir")


def test_unknown_voice_removes_previous_primary_context():
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.logger = _Logger()
    coordinator.config = SimpleNamespace(get=lambda key, default=None: {
        "user_profiles.primary_user_id": "primary_user",
    }.get(key, default))
    coordinator.profile_manager = SimpleNamespace(
        get_honorific_for=lambda user_id: "sir",
        get_formal_address_for=lambda user_id: None,
    )
    coordinator.conversation = SimpleNamespace(current_user="primary_user")
    context_users = []
    coordinator.context_window = SimpleNamespace(set_user=context_users.append)
    coordinator._last_speaker_id = "primary_user"
    coordinator._last_switch_time = 0.0
    coordinator._rapid_switch_count = 0

    coordinator._apply_speaker_context(None, 0.10)

    assert coordinator.conversation.current_user == "__guest__"
    assert get_honorific() == "Gast"
    assert context_users == ["__guest__"]


@pytest.mark.parametrize("word", ["Stopp", "Stop", "Halt"])
def test_global_stop_is_accepted_for_unknown_voice(word):
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.listener = SimpleNamespace(
        _speaking_event=threading.Event(), active_tts_text="Die Antwort läuft.",
        _capture_generation=0, invalidate_pending_audio=lambda: None,
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
    coordinator.logger = _Logger()

    assert coordinator.handle_barge_in(word, speaker_id=None, speaker_confidence=0.0)
    assert coordinator._turn_cancelled.is_set()
    assert coordinator.event_queue.empty()


@pytest.mark.parametrize("include_guest_turn", [False, True])
def test_unknown_llm_context_excludes_primary_history_and_personal_hooks(
    monkeypatch, include_guest_turn,
):
    private_turn = {"role": "user", "content": "PRIVATE_OWNER_MARKER", "user_id": "primary_user"}
    guest_turn = {"role": "user", "content": "general question", "user_id": "__guest__"}
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("personal hook")
        raise AssertionError("UNKNOWN must not read personal context")

    history = [private_turn] + ([guest_turn] if include_guest_turn else [])
    def selected_history(kwargs):
        target = kwargs.get("target_history")
        return history if target is None else target

    conversation = SimpleNamespace(
        current_user="__guest__",
        session_history=history,
        is_multi_speaker=False,
        format_history_for_llm=lambda **kwargs: "\n".join(
            item["content"] for item in selected_history(kwargs)
        ),
        get_recent_history=lambda **kwargs: selected_history(kwargs),
    )
    router = ConversationRouter.__new__(ConversationRouter)
    router.conversation = conversation
    router._target_history = None
    router.context_window = SimpleNamespace(enabled=True, assemble_context=forbidden)
    router.awareness = SimpleNamespace(assemble=forbidden)
    router.memory_manager = SimpleNamespace(
        get_proactive_context=forbidden, get_full_user_context=forbidden,
    )
    router.people_manager = SimpleNamespace(get_people_context=forbidden)
    router.self_awareness = SimpleNamespace(get_capability_manifest=forbidden)
    router.conv_state = SimpleNamespace(
        conversation_topic=None, turn_count=0,
        last_tool_result_text="PRIVATE_TOOL_MARKER",
        research_exchange=None,
        last_response_text="PRIVATE_RESPONSE_MARKER",
        last_command="private command",
    )
    monkeypatch.setattr(
        "core.debug_logger.get_debug_logger",
        lambda: SimpleNamespace(log_conversation_history=lambda **kwargs: None,
                                log_context_window=lambda **kwargs: None),
    )

    result = router._prepare_llm_context("Wie ist das Wetter?", in_conversation=True)

    assert ("general question" in result.llm_history) is include_guest_turn
    assert "PRIVATE_OWNER_MARKER" not in result.llm_history
    assert "PRIVATE_" not in result.llm_command
    assert result.context_messages is None
    assert calls == []


def test_unknown_router_greeting_preserves_pending_owner_rundown(monkeypatch):
    monkeypatch.setattr("core.persona.guest_greeting", lambda: "Neutrale Begrüßung.")
    calls = []
    reminders = SimpleNamespace(
        is_rundown_pending=lambda: True,
        deliver_rundown=lambda: calls.append("deliver"),
        has_rundown_mention=lambda: True,
        clear_rundown_mention=lambda: calls.append("clear"),
    )
    router = ConversationRouter.__new__(ConversationRouter)
    router.conversation = SimpleNamespace(current_user="__guest__")
    router.reminder_manager = reminders
    router.config = SimpleNamespace(get=lambda key, default=None: default)

    result = router._route_inner("jarvis_only")

    assert result.intent == "guest_greeting"
    assert result.text == "Neutrale Begrüßung."
    assert calls == []


def test_identified_primary_can_accept_pending_rundown():
    calls = []
    router = ConversationRouter.__new__(ConversationRouter)
    router.conversation = SimpleNamespace(current_user="primary_user")
    router.reminder_manager = SimpleNamespace(
        is_rundown_pending=lambda: True,
        deliver_rundown=lambda: calls.append("deliver"),
    )
    router.config = SimpleNamespace(get=lambda key, default=None: default)

    result = router._route_inner("ja")

    assert result.intent == "rundown_accept"
    assert calls == ["deliver"]


@pytest.mark.parametrize("tool_name", ["recall_memory", "developer_tools"])
def test_unknown_voice_rejects_forged_personal_tool_call_before_execution(
    monkeypatch, tool_name,
):
    class _Timer:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def cancel(self):
            pass

    executed = []
    monkeypatch.setattr("core.pipeline.threading.Timer", _Timer)
    monkeypatch.setattr(
        "core.tool_executor.execute_tool",
        lambda name, arguments: executed.append(name),
    )
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.conversation = SimpleNamespace(current_user="__guest__")
    coordinator.conv_state = SimpleNamespace(jarvis_asked_question=False)
    coordinator._classify_ack = lambda *args, **kwargs: ("none", None)
    coordinator._turn_cancelled = threading.Event()
    coordinator._current_latency = None
    coordinator.logger = _Logger()
    coordinator.tts = SimpleNamespace(engine="piper")
    coordinator.web_researcher = None
    coordinator.llm = SimpleNamespace(
        tool_calling=True,
        stream_with_tools=lambda **kwargs: iter([ToolCallRequest(tool_name, {})]),
    )

    result = coordinator._stream_llm_response(
        "Allgemeine Frage", "", use_tools=[{"function": {"name": tool_name}}],
    )

    assert "erkannte Stimme" in result
    assert executed == []
