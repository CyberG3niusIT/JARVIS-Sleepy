"""Direct-audio routing: Gemma PRIMARY hears the audio, Qwen EXPERT stays out.

All fakes, no network: requests.post is monkeypatched and health probes are
stubbed.
"""

import base64
import io
import json
import threading
import time
import wave

import numpy as np

from core.direct_audio import AUDIO_TURN_PROMPT, DirectAudioService, store_user_turn
from core.llm_router import LLMRouter

PRIMARY = "http://127.0.0.1:8080/v1/chat/completions"
EXPERT = "http://127.0.0.1:8082/v1/chat/completions"


class Cfg:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def make_config(**extra):
    values = {
        "llm.primary.endpoint": PRIMARY,
        "llm.primary.provider": "gemma",
        "llm.primary.model_path": "/nonexistent/gemma.gguf",
        "llm.primary.audio_direct": True,
        "llm.primary.tool_calling": False,
        "llm.primary.temperature": 0.7,
        "llm.primary.top_p": 0.95,
        "llm.primary.top_k": 64,
        "llm.expert.endpoint": EXPERT,
        "llm.expert.provider": "qwen",
        "llm.expert.model_path": "/nonexistent/qwen.gguf",
        "llm.expert.enable_thinking": False,
        "llm.local.endpoint": PRIMARY,
        "llm.local.llama_completion": "",
        "stt.wake_compat": True,
        "llm.primary.stt_verdict_timeout_s": 0,      # verdict hold has its own tests
    }
    values.update(extra)
    return Cfg(values)


class FakeResponse:
    status_code = 200

    def __init__(self, tokens=("Guten", " Tag")):
        self._tokens = tokens

    def iter_lines(self):
        for tok in self._tokens:
            yield ("data: " + json.dumps({"choices": [{"delta": {"content": tok}}]})).encode()
        yield b"data: [DONE]"

    def raise_for_status(self):
        pass

    def close(self):
        pass

    def json(self):
        return {}


class PostRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, url, json=None, timeout=None, stream=None, **kw):
        self.calls.append({"url": url, "json": json})
        return FakeResponse()


def fake_wav_b64():
    return LLMRouter.encode_audio_wav_b64(np.zeros(1600, dtype=np.float32))


# ---------------------------------------------------------------------------
# Router: payload + endpoints
# ---------------------------------------------------------------------------

def test_encode_audio_wav_b64_is_16k_mono_pcm16():
    audio = np.linspace(-1.0, 1.0, 16000, dtype=np.float32)
    raw = base64.b64decode(LLMRouter.encode_audio_wav_b64(audio))
    with wave.open(io.BytesIO(raw)) as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 16000
        assert wav.getnframes() == 16000


def test_build_user_message_audio_item():
    b64 = fake_wav_b64()
    msg = LLMRouter._build_user_message("hi", audio_data=b64)
    assert msg["role"] == "user"
    audio_parts = [p for p in msg["content"] if p["type"] == "input_audio"]
    assert audio_parts == [{"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}}]
    assert LLMRouter._build_user_message("hi") == {"role": "user", "content": "hi"}


def test_audio_turn_request_has_input_audio_and_targets_primary(monkeypatch):
    rec = PostRecorder()
    monkeypatch.setattr("core.llm_router.requests.post", rec)
    router = LLMRouter(make_config())
    b64 = fake_wav_b64()

    tokens = list(router.stream("Sprachaufnahme", audio_data=b64))

    assert tokens == ["Guten", " Tag"]
    assert len(rec.calls) == 1
    call = rec.calls[0]
    assert call["url"] == PRIMARY
    last = call["json"]["messages"][-1]
    assert {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}} in last["content"]
    # Gemma 4 must not think: reasoning_content would leave `content` empty
    assert call["json"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert router.last_call_info["provider"] == "gemma"


def test_stream_with_tools_carries_audio_and_no_qwen_penalty(monkeypatch):
    rec = PostRecorder()
    monkeypatch.setattr("core.llm_router.requests.post", rec)
    router = LLMRouter(make_config(**{"llm.primary.tool_calling": True}))
    b64 = fake_wav_b64()
    tools = [{"type": "function", "function": {"name": "web_search",
                                               "description": "d", "parameters": {"type": "object", "properties": {}}}}]

    list(router.stream_with_tools("Sprachaufnahme", tools=tools, audio_data=b64,
                                  tool_presence_penalty=1.5))

    payload = rec.calls[0]["json"]
    assert rec.calls[0]["url"] == PRIMARY
    assert "presence_penalty" not in payload          # Qwen-only tuning
    assert any(p.get("type") == "input_audio" for p in payload["messages"][-1]["content"])
    assert router.last_call_info["provider"] == "gemma"


def test_normal_turn_never_touches_expert_endpoint(monkeypatch):
    rec = PostRecorder()
    monkeypatch.setattr("core.llm_router.requests.post", rec)
    router = LLMRouter(make_config(**{"llm.primary.tool_calling": True}))

    list(router.stream("hallo"))
    list(router.stream_with_tools("hallo", tools=None))
    list(router.stream("x", audio_data=fake_wav_b64()))

    assert rec.calls
    assert {c["url"] for c in rec.calls} == {PRIMARY}


def test_expert_role_uses_expert_endpoint_and_qwen_params(monkeypatch):
    rec = PostRecorder()
    monkeypatch.setattr("core.llm_router.requests.post", rec)
    router = LLMRouter(make_config())

    list(router.stream("schwere Frage", role="expert"))

    assert rec.calls[0]["url"] == EXPERT
    assert rec.calls[0]["json"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert rec.calls[0]["json"]["top_k"] == 20
    assert router.last_call_info["provider"] == "qwen"


def test_expert_without_endpoint_is_never_replaced_by_primary(monkeypatch):
    rec = PostRecorder()
    monkeypatch.setattr("core.llm_router.requests.post", rec)
    cfg = make_config()
    cfg.values.pop("llm.expert.endpoint")
    router = LLMRouter(cfg)

    assert list(router.stream("x", role="expert")) == []
    assert rec.calls == []


def test_llm_local_alias_still_resolves_to_primary():
    router = LLMRouter(Cfg({"llm.local.endpoint": "http://127.0.0.1:9080/v1/chat/completions",
                            "llm.local.llama_completion": ""}))
    assert router.local_endpoint == "http://127.0.0.1:9080/v1/chat/completions"
    assert router.resolve_role("primary")["provider"] == "qwen"     # legacy-only setup
    router = LLMRouter(make_config())
    assert router.resolve_role(None)["endpoint"] == PRIMARY
    assert router.resolve_role("expert")["endpoint"] == EXPERT


# ---------------------------------------------------------------------------
# DirectAudioService: readiness, no fake fallback, STT independence
# ---------------------------------------------------------------------------

class FakeLLM:
    tool_calling = False

    def __init__(self, states=("READY",)):
        self.states = list(states)
        self.probe_calls = 0
        self.stream_calls = []
        self.stream_started = threading.Event()
        self.cancelled = 0
        self.encode_audio_wav_b64 = LLMRouter.encode_audio_wav_b64

    def probe_role(self, role=None, ttl=None, timeout=1.0):
        self.probe_calls += 1
        if len(self.states) > 1:
            return self.states.pop(0)
        return self.states[0]

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        self.stream_started.set()
        yield "Antwort"

    def stream_with_tools(self, **kwargs):
        self.stream_calls.append(kwargs)
        self.stream_started.set()
        yield "Antwort"

    def cancel_active_stream(self):
        self.cancelled += 1


AUDIO = np.zeros(16000, dtype=np.float32)


def drain(at, timeout=2.0):
    out = []
    t0 = time.monotonic()
    it = at.turn.stream()
    for item in it:
        out.append(item)
        if time.monotonic() - t0 > timeout:
            break
    return out


def test_ready_primary_starts_immediately_with_audio_and_primary_role():
    llm = FakeLLM(["READY"])
    svc = DirectAudioService(llm, make_config())

    at = svc.start_turn(AUDIO, generation=3, in_conversation=True)

    assert at is not None and at.mode == "direct"
    assert drain(at) == ["Antwort"]
    kw = llm.stream_calls[0]
    assert kw["role"] == "primary"
    assert kw["user_message"] == AUDIO_TURN_PROMPT
    assert base64.b64decode(kw["audio_data"])[:4] == b"RIFF"
    assert at.audio is None                      # raw samples dropped after encoding


def test_stt_result_does_not_delay_or_replace_gemma_request():
    llm = FakeLLM(["READY"])
    svc = DirectAudioService(llm, make_config())
    stt_gate = threading.Event()                 # STT "finishes" only when set - never here

    at = svc.start_turn(AUDIO, in_conversation=True)

    assert llm.stream_started.wait(1.0), "request must start without any STT result"
    assert not stt_gate.is_set()
    # STT arrives later: metadata only, request content unchanged
    svc.note_transcript(at.turn_id, "aura wie spät ist es")
    assert at.asr_hint == "aura wie spät ist es"
    kw = llm.stream_calls[0]
    assert "spät" not in json.dumps({k: v for k, v in kw.items() if k != "audio_data"}, default=str)
    assert len(llm.stream_calls) == 1


def test_not_ready_without_fallback_waits_starting_and_never_fakes_fallback():
    llm = FakeLLM(["STARTING", "STARTING", "READY"])
    sleeps = []
    svc = DirectAudioService(llm, make_config(**{"llm.primary.ready_wait_s": 30}),
                             sleep=lambda s: sleeps.append(s), poll_interval=0.01)

    at = svc.start_turn(AUDIO, in_conversation=True)

    assert at is not None and at.mode == "wait"          # queued, honest
    assert drain(at) == ["Antwort"]                       # answered only once READY
    assert sleeps                                          # it really waited
    assert svc.status == "READY"
    assert len(llm.stream_calls) == 1                     # single model request, no fallback call


def test_not_ready_stays_starting_and_fails_honestly_after_timeout():
    llm = FakeLLM(["STARTING"])
    clock = {"t": 0.0}

    def mono():
        return clock["t"]

    def fake_sleep(s):
        clock["t"] += 10.0

    svc = DirectAudioService(llm, make_config(**{"llm.primary.ready_wait_s": 25}),
                             sleep=fake_sleep, monotonic=mono, poll_interval=1)
    at = svc.start_turn(AUDIO, in_conversation=True)

    assert at.mode == "wait"
    assert drain(at) == []                                # no invented answer
    assert at.failure == "primary_unavailable"
    assert svc.status == "STARTING"
    assert llm.stream_calls == []


def test_not_ready_with_configured_fallback_returns_none_for_text_path():
    llm = FakeLLM(["STARTING"])
    svc = DirectAudioService(llm, make_config(), text_fallback_available=lambda: True)
    assert svc.start_turn(AUDIO, in_conversation=True) is None
    assert llm.stream_calls == []


def test_disabled_direct_audio_returns_none():
    llm = FakeLLM(["READY"])
    svc = DirectAudioService(llm, make_config(**{"llm.primary.audio_direct": False}))
    assert svc.start_turn(AUDIO) is None
    assert llm.probe_calls == 0


class FakeConversation:
    def __init__(self):
        self.session_history = []
        self.persisted = []

    def add_message(self, role, content, asr_hint=None, audio_turn_id=None, **kw):
        msg = {"role": role, "content": content}
        if audio_turn_id:
            msg["audio_turn_id"] = audio_turn_id
        if asr_hint:
            msg["asr_hint"] = asr_hint
        self.session_history.append(msg)
        self.persisted.append({k: v for k, v in msg.items() if k != "asr_hint"})  # history file


def test_conversation_state_stores_processed_turn_asr_only_as_hint():
    llm = FakeLLM(["READY"])
    svc = DirectAudioService(llm, make_config())
    at = svc.start_turn(AUDIO, in_conversation=True)
    svc.note_transcript(at.turn_id, "wie spät ist es")
    conv = FakeConversation()

    store_user_turn(conv, at)

    msg = conv.session_history[-1]
    assert msg["content"] == at.placeholder != "wie spät ist es"
    assert msg["audio_turn_id"] == at.turn_id
    assert msg["asr_hint"] == "wie spät ist es"          # metadata only
    assert "asr_hint" not in conv.persisted[-1]           # never persisted as user text


def test_asr_hint_dropped_when_content_logging_not_allowed():
    svc = DirectAudioService(FakeLLM(["READY"]), make_config(), content_allowed=lambda: False)
    at = svc.start_turn(AUDIO, in_conversation=True)
    svc.note_transcript(at.turn_id, "geheim")
    assert at.asr_hint is None


def test_privacy_flush_discards_turns_audio_and_hints():
    llm = FakeLLM(["STARTING"])
    svc = DirectAudioService(llm, make_config(), sleep=lambda s: time.sleep(0.01), poll_interval=0.01)
    at = svc.start_turn(AUDIO, in_conversation=False)
    svc.note_transcript(at.turn_id, "text")

    assert svc.discard_all() == 1

    assert svc.get(at.turn_id) is None
    assert at.asr_hint is None and at.audio is None
    assert at.turn.is_rejected


def test_system_prompt_pins_german_and_audio_prompt_says_german():
    router = LLMRouter(make_config())
    assert "ausschließlich Deutsch" in router._build_system_prompt()
    assert "ausschließlich Deutsch" in router._build_system_prompt(guest_mode=True)
    assert "Deutsch" in AUDIO_TURN_PROMPT
