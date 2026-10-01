"""Content-free turn cleanup and explicit-search topic regressions."""
from types import SimpleNamespace
from unittest.mock import Mock
import threading
import pytest

from core.conversation_router import ConversationRouter, extract_explicit_search_query
from core.events import Event, EventType, PipelineState
from core.latency_tracker import LatencyTracker
from core.pipeline import Coordinator


@pytest.mark.parametrize("command, expected", [
    ("Suche im Web nach Python List Comprehensions und erkläre sie kurz.", "Python List Comprehensions"),
    ("Bitte suche im Internet nach synthetic-topic.", "synthetic-topic"),
    ("Suche im Web nach Wetter und schalte das Licht an", None),
    ("Suche im Web nach Wetter und zeige meine Termine", None),
    ("Suche im Web nach Thema und speichere ein Dokument", None),
    ("Suche nicht im Web nach Thema", None),
    ("Was sind List Comprehensions?", None),
])
def test_explicit_search_topic(command, expected):
    assert extract_explicit_search_query(command) == expected


@pytest.mark.parametrize("failure", [False, True])
def test_command_finalization_resumes_exactly_once_and_clears_watchdog(failure):
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.listener = SimpleNamespace(resume_listening=Mock())
    coordinator.logger = Mock()
    coordinator.config = None
    coordinator.running = True
    coordinator._active_audio_pipeline = None
    coordinator._current_latency = LatencyTracker("synthetic-turn")
    coordinator._last_command_start_ts = 1.0
    coordinator.state = PipelineState.PROCESSING_COMMAND
    def implementation(event):
        if failure:
            raise RuntimeError("synthetic-bookkeeping-failure")
        coordinator.listener.resume_listening()
        coordinator.state = PipelineState.IDLE
    coordinator._handle_command_impl = implementation
    if failure:
        with pytest.raises(RuntimeError):
            coordinator._handle_command(Event(EventType.COMMAND_DETECTED, "synthetic"))
    else:
        coordinator._handle_command(Event(EventType.COMMAND_DETECTED, "synthetic"))
    assert coordinator.state is PipelineState.IDLE
    assert coordinator._last_command_start_ts == 0.0
    coordinator.listener.resume_listening.assert_called_once()
    assert coordinator._current_latency is None


def test_finalization_never_resumes_stopped_runtime():
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.listener = SimpleNamespace(resume_listening=Mock())
    coordinator.running = False
    coordinator.state = PipelineState.PROCESSING_COMMAND
    coordinator._current_latency = None
    coordinator._handle_command_impl = Mock()
    coordinator._handle_command(Event(EventType.COMMAND_DETECTED))
    coordinator.listener.resume_listening.assert_not_called()


def test_explicit_search_preserves_query_and_speaks_before_continuation_finishes(monkeypatch):
    from core.llm_router import ToolCallRequest
    from core.web_research import SearchOutcome
    monkeypatch.setattr("core.pipeline.threading.Timer", lambda *a, **kw: Mock())
    monkeypatch.setattr("core.event_logger.get_event_logger", lambda: None)
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.conversation = SimpleNamespace(current_user="synthetic-owner")
    coordinator.conv_state = SimpleNamespace(jarvis_asked_question=False)
    coordinator._classify_ack = lambda *a, **kw: ("none", None)
    coordinator._play_ack_if_still_thinking = Mock()
    coordinator._turn_cancelled = threading.Event()
    coordinator._current_latency = LatencyTracker("synthetic-search")
    coordinator.logger = Mock()
    coordinator.tts = SimpleNamespace(engine="piper", ack_played=False, _spoke=False)
    coordinator.listener = SimpleNamespace(active_tts_text="")
    coordinator.interaction_cache = None
    coordinator.memory_manager = None
    coordinator._speak_and_wait = Mock()
    coordinator.web_researcher = SimpleNamespace(
        search=Mock(return_value=SearchOutcome("success", [{
            "title": "Synthetic", "url": "https://example.invalid/public", "snippet": "Synthetic evidence",
        }], backend="synthetic")),
        fetch_pages_parallel=Mock(return_value=[]))
    spoken = []
    def process(chunk, *args):
        spoken.append(chunk)
        # Return counts/flags/pending/pipeline expected by the real stream loop.
        return 1, True, None, None
    coordinator._process_speech_chunk = process
    def continuation(*args, **kwargs):
        assert kwargs["tools"] == []
        yield "Synthetischer erster Satz. "
        assert spoken == ["Synthetischer erster Satz."]
        yield "Synthetischer zweiter Satz. "
    coordinator.llm = SimpleNamespace(
        tool_calling=True,
        stream_with_tools=lambda **kw: iter([ToolCallRequest("web_search", {"query": "incorrect-topic"}, call_id="synthetic")]),
        continue_after_tool_call=continuation,
        chat=Mock(side_effect=AssertionError("Unexpected fallback")),
        strip_filler=lambda text: text,
        strip_metric=lambda text, command: text,
        _check_response_quality=lambda *a: None)
    command = "Suche im Web nach Python List Comprehensions und erkläre sie kurz."
    response = coordinator._stream_llm_response(command, "", force_web_search=True)
    assert "Synthetischer zweiter Satz" in response
    coordinator.web_researcher.search.assert_called_once_with("Python List Comprehensions", max_results=5)
    coordinator.llm.chat.assert_not_called()


@pytest.mark.parametrize("command, period, planning", [
    ("Kalender heute", "today", False),
    ("Kalender morgen", "tomorrow", False),
    ("Kalender diese Woche", "week", False),
    ("Was steht heute an?", "today", False),
    ("Plane meinen Tag", "today", True),
    ("Reminder heute", "today", False),
    ("Was steht heute in meinem Kalender?", "today", False),
    ("Was steht morgen an?", "tomorrow", False),
    ("Was habe ich diese Woche?", "week", False),
    ("Welche Erinnerungen habe ich heute?", "today", False),
])
def test_day_overview_is_read_only_and_keeps_current_identity(monkeypatch, command, period, planning):
    helper = Mock()
    helper.get_overview.return_value = "synthetic-overview"
    factory = Mock(return_value=helper)
    monkeypatch.setattr("core.day_partner.DayPartner", factory)
    router = ConversationRouter.__new__(ConversationRouter)
    router.reminder_manager = SimpleNamespace(_calendar_manager="synthetic-calendar")
    router.conversation = SimpleNamespace(current_user="synthetic-owner")
    result = router._handle_day_overview(command)
    assert result.handled and result.source == "day_partner"
    kwargs = dict(period=period, planning=planning, created_by="synthetic-owner")
    if command.startswith(("Reminder", "Welche Erinnerungen")):
        kwargs["sources"] = "reminders"
    helper.get_overview.assert_called_once_with(**kwargs)
    factory.assert_called_once_with(router.reminder_manager, calendar_manager="synthetic-calendar")


def test_failed_turn_latency_never_emits_success(monkeypatch):
    event_logger = Mock()
    monkeypatch.setattr("core.event_logger.get_event_logger", lambda *a: event_logger)
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.listener = SimpleNamespace(resume_listening=Mock())
    coordinator.logger = Mock()
    coordinator.config = None
    coordinator.running = True
    coordinator.state = PipelineState.PROCESSING_COMMAND
    coordinator._current_latency = LatencyTracker("synthetic-failure")
    coordinator._handle_command_impl = Mock(side_effect=RuntimeError("synthetic"))
    with pytest.raises(RuntimeError):
        coordinator._handle_command(Event(EventType.COMMAND_DETECTED))
    assert event_logger.emit.call_args.kwargs["status"] == "error"


def test_audio_finish_deadline_cancels_owned_playback(monkeypatch):
    from core.pipeline import StreamingAudioPipeline
    pipeline = StreamingAudioPipeline.__new__(StreamingAudioPipeline)
    pipeline._cancelled = threading.Event()
    pipeline._text_queue = Mock()
    pipeline._done = SimpleNamespace(wait=Mock(return_value=False))
    pipeline._error = None
    pipeline.logger = Mock()
    pipeline.cancel = Mock()
    clock = iter([1.0, 122.0])
    monkeypatch.setattr("core.pipeline.time.monotonic", lambda: next(clock))
    pipeline.finish()
    pipeline.cancel.assert_called_once()


@pytest.mark.parametrize("command, method", [
    ("Erstelle einen Termin morgen um 17 Uhr für den Einkauf", "create_calendar_event"),
    ("Lösche den Termin Einkauf aus dem Kalender", "delete_calendar_event"),
    ("Verschiebe den Termin Einkauf auf morgen um 17 Uhr", "update_calendar_event"),
])
def test_calendar_write_routes_existing_confirmation_skill_only(command, method):
    skill = SimpleNamespace(**{method: Mock(return_value="synthetic-confirmation")})
    router = ConversationRouter.__new__(ConversationRouter)
    router.skill_manager = SimpleNamespace(skills={"google_calendar": skill})
    result = router._handle_calendar_write(command)
    assert result.handled and result.source == "calendar_confirmation"
    assert skill._last_user_text == command
    getattr(skill, method).assert_called_once_with()


def test_calendar_create_flow_stops_at_existing_confirmation(monkeypatch):
    from skills.personal.google_calendar.skill import GoogleCalendarSkill
    monkeypatch.setattr("skills.personal.google_calendar.skill.get_privacy_gate",
                        lambda: SimpleNamespace(allow=lambda capability: True))
    manager = SimpleNamespace(is_connected=True, _jarvis_calendar_id="synthetic-calendar",
                              can_access_user=lambda user: user == "synthetic-owner",
                              create_event=Mock(), update_event=Mock(), delete_event=Mock())
    skill = GoogleCalendarSkill.__new__(GoogleCalendarSkill)
    skill.conversation = SimpleNamespace(current_user="synthetic-owner")
    # BaseSkill dependency injection uses the shared reminder manager.
    skill._manager_ref = manager
    router = ConversationRouter.__new__(ConversationRouter)
    router.skill_manager = SimpleNamespace(skills={"google_calendar": skill})
    result = router._handle_calendar_write("Erstelle einen Termin morgen um 17 Uhr für Testtermin")
    assert result.source == "calendar_confirmation"
    assert "Ja oder Nein" in result.text
    assert skill._pending_confirmation[0] == "create"
    assert skill._pending_confirmation[1]["start_time"].hour == 17
    manager.create_event.assert_not_called()
    manager.update_event.assert_not_called()
    manager.delete_event.assert_not_called()


def test_speech_end_is_actual_positive_frame_receipt_not_silence_estimate(monkeypatch):
    import numpy as np
    import queue
    from core.continuous_listener import ContinuousListener
    listener = ContinuousListener.__new__(ContinuousListener)
    listener._callback_count = 0
    listener._callback_last_log = 100.0
    listener._callback_heartbeat_interval = 60.0
    listener._privacy_gate = SimpleNamespace(allow=lambda capability: True)
    listener.use_rnnoise = False
    listener.device_sample_rate = listener.sample_rate = 16000
    listener.frame_size = 512
    listener._speaking_event = threading.Event()
    listener.speaking = False
    listener._barge_in_enabled = False
    listener._diag_audio = False
    listener.collecting_speech = False
    listener.vad = SimpleNamespace(silence_frames=0, process_frame=lambda audio: (True, False))
    times = iter([101.0, 102.0])
    monkeypatch.setattr("core.continuous_listener.time.monotonic", lambda: next(times))
    listener._audio_callback(np.zeros(512, dtype=np.float32), 512, None, None)
    assert listener._last_speech_end_ts == 101.0
    listener.vad.silence_frames = 20
    listener.vad.process_frame = lambda audio: (False, True)
    listener._audio_callback(np.zeros(512, dtype=np.float32), 512, None, None)
    assert listener._last_speech_end_ts == 101.0
    listener._turn_assembler = None
    listener.audio_queue = queue.Queue()
    listener._submit_segment(np.zeros(512, dtype=np.float32), 1, False)
    assert listener.audio_queue.get_nowait()["speech_end"] == 101.0
