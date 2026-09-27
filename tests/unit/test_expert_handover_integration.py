"""Integration: Coordinator <-> ModelHandover <-> delegate_to_expert (all fakes).

No real systemctl / llama-server. Covers: the delegator drives ModelHandover, the expert
answer is delivered ONCE and BEFORE the primary is READY again, ordinary (math) turns never
touch the expert, router model_role='expert' goes through the handover (never a direct
role='expert' stream), and requests queue honestly while the primary is STARTING.
"""

import queue
import threading
import time
from types import SimpleNamespace

from core.conversation_router import RouteResult
from core.events import Event, EventType, PipelineState
from core.model_handover import HandoverState, ModelHandover
from core.pipeline import Coordinator
from core.tools import delegate_to_expert as tool

P, E = "llama-server-primary.service", "llama-server-expert.service"


class FakeSystem:
    def __init__(self):
        self.active = {P}
        self.log = []
        self.primary_gate = threading.Event()
        self.primary_gate.set()
        self.now = 0.0

    def systemctl(self, action, unit):
        self.log.append((action, unit))
        if action == "is-active":
            return 0, "active" if unit in self.active else "inactive"
        if action == "stop":
            self.active.discard(unit)
            return 0, ""
        if action == "start":
            self.active.add(unit)
            return 0, ""
        raise AssertionError(action)

    def health(self, role):
        unit = P if role == "primary" else E
        if role == "primary" and not self.primary_gate.is_set():
            return False
        return unit in self.active

    def port_listening(self, role):
        return (P if role == "primary" else E) in self.active

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        time.sleep(0.001)


class Cfg:
    def __init__(self, **values):
        self.values = {
            "handover.stop_timeout_s": 5, "handover.primary_start_timeout_s": 100000,
            "handover.expert_start_timeout_s": 100000, "handover.vram_release_wait_s": 2,
            "handover.poll_interval_s": 1, "llm.expert.endpoint": "http://127.0.0.1:8082/v1/chat/completions",
        }
        self.values.update(values)

    def get(self, key, default=None):
        return self.values.get(key, default)


class FakeLLM:
    def __init__(self, handover_ref):
        self.handover_ref = handover_ref
        self.chat_calls = []
        self.stream_calls = []

    def resolve_role(self, role=None):
        return {"role": role}

    def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        assert kwargs["role"] == "expert"
        return "Expertenantwort"

    def strip_metric(self, text, command=""):
        return text

    def strip_filler(self, text):
        return text

    def cancel_active_stream(self):
        pass


class FakeConversation:
    current_user = "alex"
    request_follow_up = None

    def __init__(self):
        self.session_history = []

    def add_message(self, role, content, **kwargs):
        self.session_history.append({"role": role, "content": content})

    def format_history_for_llm(self, include_system_prompt=False):
        return "history"

    def get_conversation_stats(self):
        return {"session_user_messages": 1, "session_assistant_messages": 1}


def make(tmp_path, monkeypatch, cfg=None, fallback=None):
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path))
    system = FakeSystem()
    config = cfg or Cfg()
    handover = ModelHandover(config, systemctl=system.systemctl, health=system.health,
                             port_listening=system.port_listening, clock=system.clock,
                             sleep=system.sleep, fallback_available=fallback, state_dir=tmp_path)
    coord = Coordinator.__new__(Coordinator)
    coord.config = config
    coord.logger = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None,
                                   debug=lambda *a, **k: None, error=lambda *a, **k: None)
    coord.llm = FakeLLM(handover)
    coord.conversation = FakeConversation()
    coord.conv_state = SimpleNamespace(update=lambda **k: None, jarvis_asked_question=False,
                                       last_intent="")
    coord._turn_cancelled = threading.Event()
    coord.handover = None
    coord._pending_expert = None
    coord.spoken = []
    coord._speak_and_wait = coord.spoken.append
    coord._manage_conversation_window = lambda *a, **k: None
    coord.attach_handover(handover)
    return coord, handover, system


def teardown_function(_):
    tool.set_expert_delegator(None)


def test_delegator_runs_handover_and_delivers_before_primary_ready(tmp_path, monkeypatch):
    coord, handover, system = make(tmp_path, monkeypatch)
    system.primary_gate.clear()          # the primary stays "loading" after restart
    seen = []
    real_deliver = coord.deliver_expert_answer

    def deliver(text, ctx=None):
        seen.append((handover.state, handover.lifecycle_state(), handover.primary_ready))
        return real_deliver(text, ctx)

    coord.deliver_expert_answer = deliver

    reply = tool.handler({"reason": "zu schwer", "task": "Beweise den Satz"})
    assert "Experten" in reply and coord._pending_expert is not None   # accepted, runs after the turn
    request = coord._pending_expert
    coord._pending_expert = None

    coord._run_expert_turn(request)
    assert len(seen) == 1                                      # delivered exactly once
    assert seen[0][0] is HandoverState.RESTORING_PRIMARY       # ... while the primary is not READY
    assert seen[0][1:] == ("STARTING", False)
    assert coord.llm.chat_calls[0]["role"] == "expert"
    assert coord.llm.chat_calls[0]["user_message"] == "Beweise den Satz"
    assert "Expertenantwort" in coord.spoken                   # straight to TTS, no primary pass
    assert coord.conversation.session_history[-1] == {"role": "assistant", "content": "Expertenantwort"}

    system.primary_gate.set()
    assert handover.join_restore(10)
    assert handover.lifecycle_state() == "READY"
    order = [(a, u) for a, u in system.log if a in ("start", "stop")]
    assert order == [("stop", P), ("start", E), ("stop", E), ("start", P)]
    assert system.active == {P}


def test_expert_failure_is_spoken_honestly_and_nothing_is_delivered(tmp_path, monkeypatch):
    coord, handover, system = make(tmp_path, monkeypatch)
    coord.llm.chat = lambda **k: (_ for _ in ()).throw(RuntimeError("boom"))
    coord._run_expert_turn(tool.ExpertRequest(reason="r", task="t"))
    assert handover.join_restore(10)
    assert any("nicht antworten" in s for s in coord.spoken)
    assert not any("Expertenantwort" in s for s in coord.spoken)
    assert system.active == {P}


# --- _handle_command routing -------------------------------------------------------------

def make_command_coordinator(tmp_path, monkeypatch, route):
    coord, handover, system = make(tmp_path, monkeypatch)
    coord.event_queue = queue.Queue()
    coord.listener = SimpleNamespace(
        conversation_window_active=False, pause_listening=lambda: None,
        resume_listening=lambda: None, open_conversation_window=lambda d: None)
    coord.tts = SimpleNamespace(_spoke=False)
    coord.stats = {"commands_processed": 0}
    coord.memory_manager = None
    coord.wake_word = "aura"
    coord.state = PipelineState.IDLE
    coord.direct_audio = SimpleNamespace(pop=lambda i: None)
    coord._last_speaker_confidence = 0.9
    coord._rapid_switch_count = 0
    coord._stop_only_interrupt = False
    coord._active_response_text = ""
    coord._current_latency = None
    coord._llm_responded = False
    coord._last_command_start_ts = coord._last_command_end_ts = coord._last_idle_ts = 0.0
    coord.accumulator = None
    coord._play_beep = lambda: None
    coord._classify_ack = lambda *a, **k: ("x", True)
    coord._record_metrics = lambda *a, **k: None
    coord._extract_command = lambda text: text
    coord.router = SimpleNamespace(route=lambda command, in_conversation=False: route)
    coord.stream_calls = []

    def fake_stream(command, history, **kwargs):
        coord.stream_calls.append(kwargs)
        return "Antwort vom Primary"

    coord._stream_llm_response = fake_stream
    return coord, handover, system


def _event(text):
    return Event(EventType.COMMAND_DETECTED, data=text, source="test")


def test_model_role_expert_goes_through_handover_never_a_direct_expert_stream(tmp_path, monkeypatch):
    route = RouteResult(handled=False, intent="llm", used_llm=True, llm_command="Frag den Experten",
                        llm_history="", model_role="expert", expert_requested=True)
    coord, handover, system = make_command_coordinator(tmp_path, monkeypatch, route)
    coord._handle_command(_event("frag den experten wie viel ist 17 mal 23"))
    assert handover.join_restore(10)
    assert coord.stream_calls == []                       # no direct (primary or expert) stream
    assert [c["role"] for c in coord.llm.chat_calls] == ["expert"]
    assert ("stop", P) in system.log and ("start", E) in system.log   # via the handover
    assert "Expertenantwort" in coord.spoken
    assert coord.state is PipelineState.IDLE


def test_stream_llm_response_refuses_direct_expert_role(tmp_path, monkeypatch):
    coord, _, _ = make(tmp_path, monkeypatch)
    seen = {}

    class Stop(Exception):
        pass

    def boom(**kw):
        seen.update(kw)
        raise Stop

    coord.llm.tool_calling = False
    coord.llm.stream = boom
    coord.conv_state.jarvis_asked_question = False
    coord.tts = SimpleNamespace(engine="piper")
    coord._classify_ack = lambda *a, **k: ("x", True)
    coord._llm_responded = False
    coord._current_latency = None
    coord._play_ack_if_still_thinking = lambda *a, **k: None
    coord.web_researcher = None
    try:
        coord._stream_llm_response("hi", "", role="expert")
    except Exception:
        pass
    assert seen.get("role") is None


def test_ordinary_math_question_stays_on_primary_and_never_calls_expert(tmp_path, monkeypatch):
    route = RouteResult(handled=False, intent="llm", used_llm=True, llm_command="Was ist 17 mal 23?",
                        llm_history="")
    assert route.model_role == "primary" and not route.expert_requested
    coord, handover, system = make_command_coordinator(tmp_path, monkeypatch, route)
    coord._handle_command(_event("was ist 17 mal 23"))
    assert len(coord.stream_calls) == 1 and coord.stream_calls[0]["role"] is None
    assert coord.llm.chat_calls == []
    assert all(a not in ("start", "stop") for a, _ in system.log)   # no model swap
    assert "Antwort vom Primary" in coord.spoken


def test_expert_requested_without_handover_falls_back_to_primary_honestly(tmp_path, monkeypatch):
    route = RouteResult(handled=False, intent="llm", used_llm=True, llm_command="x", llm_history="",
                        model_role="expert", expert_requested=True)
    coord, handover, system = make_command_coordinator(tmp_path, monkeypatch, route)
    coord.attach_handover(None)
    coord._handle_command(_event("frag den experten"))
    assert coord.llm.chat_calls == []
    assert len(coord.stream_calls) == 1 and coord.stream_calls[0]["role"] is None
    assert any("nicht verfügbar" in s for s in coord.spoken)


# --- STARTING queue ------------------------------------------------------------------------

def _swap_into_restoring(coord, handover, system):
    system.primary_gate.clear()
    coord._run_expert_turn(tool.ExpertRequest(reason="r", task="t"))
    assert handover.state is HandoverState.RESTORING_PRIMARY


def test_requests_queue_while_primary_starting_then_proceed(tmp_path, monkeypatch):
    coord, handover, system = make(tmp_path, monkeypatch)
    _swap_into_restoring(coord, handover, system)
    result = {}
    thread = threading.Thread(target=lambda: result.setdefault("v", coord._await_primary()))
    thread.start()
    time.sleep(0.15)
    assert thread.is_alive()                                # waiting, not answered / not faked
    assert any("geladen" in s for s in coord.spoken)        # honest STARTING notice
    system.primary_gate.set()
    thread.join(10)
    assert result["v"] is None                              # proceed on the (real) primary
    assert handover.join_restore(10)


def test_starting_without_fallback_reports_unavailable_after_queue_window(tmp_path, monkeypatch):
    coord, handover, system = make(tmp_path, monkeypatch, cfg=Cfg(**{"handover.queue_wait_s": 0.05}))
    _swap_into_restoring(coord, handover, system)
    message = coord._await_primary()
    assert message and "nicht bereit" in message
    system.primary_gate.set()
    assert handover.join_restore(10)


def test_configured_fallback_is_used_only_when_really_available(tmp_path, monkeypatch):
    coord, handover, system = make(tmp_path, monkeypatch, cfg=Cfg(**{"handover.queue_wait_s": 0.05}),
                                   fallback=lambda: True)
    _swap_into_restoring(coord, handover, system)
    assert coord._await_primary() is None                   # real fallback configured -> proceed
    system.primary_gate.set()
    assert handover.join_restore(10)


def test_await_primary_is_noop_without_handover():
    coord = Coordinator.__new__(Coordinator)
    coord.handover = None
    assert coord._await_primary() is None
