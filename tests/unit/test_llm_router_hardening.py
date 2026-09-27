"""A3 hardening: cloud fallback gate, marker filter flush, per-stream cancel,
German strings, probe timeout cap, expert negation, delegate availability."""

import json
import threading
from datetime import datetime
from types import SimpleNamespace

import pytest

from core import expert_policy as policy
from core import llm_router as lr
from core.llm_router import (ChannelMarkerFilter, ExpertCallError, LLMRouter,
                             StreamCancelHandle, ToolCallRequest, strip_channel_markers)
from core.tools import delegate_to_expert as tool


# ── ChannelMarkerFilter ──────────────────────────────────────────────

def _feed_all(chunks):
    f = ChannelMarkerFilter()
    return "".join(f.feed(c) for c in chunks) + f.flush()


def test_marker_filter_split_open_marker_and_thought():
    text = "Hallo <|channel>thought\nnachdenken<channel|> Welt"
    for step in (1, 2, 3, 5):
        chunks = [text[i:i + step] for i in range(0, len(text), step)]
        assert _feed_all(chunks) == "Hallo  Welt"


def test_marker_filter_never_swallows_plain_text():
    assert _feed_all(["a < b ", "und <c", "> ok |", "> x"]) == "a < b und <c> ok |> x"
    assert strip_channel_markers("kein Marker") == "kein Marker"


def test_marker_filter_flush_releases_held_prefix():
    f = ChannelMarkerFilter()
    assert f.feed("Ende <|chan") == "Ende "
    assert f.flush() == "<|chan"


def _sse(*events):
    lines = []
    for e in events:
        lines.append(("data: " + json.dumps(e)).encode())
    lines.append(b"data: [DONE]")
    return lines


class _Resp:
    status_code = 200

    def __init__(self, lines):
        self._lines = lines
        self.closed = False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        return iter(self._lines)

    def close(self):
        self.closed = True


def _router():
    r = LLMRouter.__new__(LLMRouter)
    r.logger = SimpleNamespace(**{n: (lambda *a, **k: None)
                                  for n in ("debug", "info", "warning", "error")})
    r._privacy_gate = SimpleNamespace(allow=lambda cap: True)
    r.config = SimpleNamespace(get=lambda k, d=None: d)
    r.last_call_chain = []
    r.last_call_info = None
    r.small_model_enabled = False
    r.small_endpoint = None
    r.home_location = None
    r.local_model_path = "m.gguf"
    r.local_endpoint = "http://x/v1/chat/completions"
    r.temperature, r.top_p, r.top_k = 0.5, 0.9, 40
    r.tool_calling = True
    r.primary_provider = "gemma"
    r.audio_direct = False
    r._record_call = lambda info: None
    r._build_system_prompt = lambda guest_mode=False: "sys"
    r._estimate_max_tokens = lambda m: 50
    return r


def test_stream_with_tools_flushes_held_text_before_tool_call(monkeypatch):
    lines = _sse(
        {"choices": [{"delta": {"content": "Moment <|chan"}}]},
        {"choices": [{"delta": {"tool_calls": [{"id": "c1", "function": {"name": "web_search",
                                                                       "arguments": "{\"query\": \"x\"}"}}]}}]},
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
    )
    monkeypatch.setattr(lr.requests, "post", lambda *a, **k: _Resp(lines))
    monkeypatch.setattr("core.debug_logger.get_debug_logger",
                        lambda: SimpleNamespace(_write=lambda *a, **k: None,
                                                log_llm_messages=lambda *a, **k: None))
    r = _router()
    out = list(r.stream_with_tools("frage", tools=[lr.WEB_SEARCH_TOOL]))
    assert out[0] == "Moment "
    assert out[1] == "<|chan"
    assert isinstance(out[-1], ToolCallRequest) and out[-1].name == "web_search"
    assert out[-1].messages is not None      # per-stream messages travel with the request


# ── per-stream cancel ────────────────────────────────────────────────

def test_cancel_handle_only_closes_its_own_stream():
    r = _router()
    a, b = r.create_stream_handle(), r.create_stream_handle()
    ra, rb = _Resp([]), _Resp([])
    r._open_stream(a), r._open_stream(b)
    a.set_response(ra)
    b.set_response(rb)
    r.cancel_active_stream(a)
    assert ra.closed and a.cancelled
    assert not rb.closed and not b.cancelled


def test_cancel_without_handle_cancels_all_active_streams():
    r = _router()
    a, b = r.create_stream_handle(), r.create_stream_handle()
    ra, rb = _Resp([]), _Resp([])
    r._open_stream(a), r._open_stream(b)
    a.set_response(ra)
    b.set_response(rb)
    r.cancel_active_stream()
    assert ra.closed and rb.closed


def test_new_stream_does_not_clear_other_streams_cancel(monkeypatch):
    lines = _sse({"choices": [{"delta": {"content": "hi"}}]})
    monkeypatch.setattr(lr.requests, "post", lambda *a, **k: _Resp(lines))
    r = _router()
    a = r.create_stream_handle()
    a.cancel()
    assert "".join(r.stream("x")) == "hi"     # stream B unaffected
    assert a.cancelled                          # ...and A stays cancelled


def test_handle_cancelled_before_response_closes_it_on_arrival():
    h = StreamCancelHandle()
    h.cancel()
    resp = _Resp([])
    h.set_response(resp)
    assert resp.closed


# ── cloud fallback ───────────────────────────────────────────────────

def test_expert_chat_never_falls_back_to_cloud(monkeypatch):
    r = _router()
    r.fallback_enabled = True
    r.api_key_env = "K"
    r.config = SimpleNamespace(get=lambda k, d=None: d, get_env=lambda k, d=None: "sekret")
    r.stream = lambda *a, **k: iter(())
    called = []
    r._generate_api_chat = lambda *a, **k: called.append(1) or "cloud"
    with pytest.raises(ExpertCallError):
        r.chat("hi", role="expert")
    with pytest.raises(ExpertCallError):
        r.chat("hi", role="expert", use_api=True)
    assert r.chat("hi", audio_data="AAAA") == ""
    assert called == []


def test_primary_text_fallback_needs_flag_and_key():
    r = _router()
    r.fallback_enabled = True
    cfg = {
        "llm.primary.text_fallback": False,
        "llm.api.enabled": True,
        "llm.api.provider": "openrouter",
        "llm.api.model": "test/model",
        "llm.api.api_key_env": "OPENROUTER_API_KEY",
        "llm.api.endpoint": "https://cloud.invalid/v1/chat/completions",
    }
    r.config = SimpleNamespace(get=lambda k, d=None: cfg.get(k, d), get_env=lambda k, d=None: "sekret")
    assert r._primary_text_fallback_allowed() is False
    cfg["llm.primary.text_fallback"] = True
    assert r._primary_text_fallback_allowed() is True
    r.config.get_env = lambda k, d=None: None
    assert r._primary_text_fallback_allowed() is False
    del cfg["llm.primary.text_fallback"]          # unset -> legacy fallback_enabled
    r.config.get_env = lambda k, d=None: "sekret"
    assert r._primary_text_fallback_allowed() is True


def test_generate_api_chat_respects_privacy_gate():
    r = _router()
    r._privacy_gate = SimpleNamespace(allow=lambda cap: False)
    assert r._generate_api_chat("x") == ""


# ── German strings / date ────────────────────────────────────────────

def test_german_date_and_messages():
    assert lr._german_date(datetime(2026, 9, 25)) == "Freitag, 25. September 2026"
    src = open(lr.__file__, encoding="utf-8").read()
    assert "I'm sorry" not in src and "REMINDER: You MUST" not in src
    assert "%B %d, %Y" not in src


def test_unavailable_text_umlaut():
    assert tool.UNAVAILABLE_TEXT == "Der Experte ist derzeit nicht verfügbar."


# ── probe_role ───────────────────────────────────────────────────────

def test_probe_role_caps_timeout(monkeypatch):
    seen = {}

    def fake_get(url, timeout):
        seen["t"] = timeout
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(lr.requests, "get", fake_get)
    r = _router()
    r._health_cache = {}
    assert r.probe_role("primary", ttl=0.0, timeout=5.0) == "READY"
    assert seen["t"] <= 0.3


# ── expert_policy negation ───────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Frag den Experten bitte nicht",
    "Lass den Experten in Ruhe",
    "Ohne Experten bitte",
    "Ich will keinen Experten fragen, frag den Experten nicht",
    "Bitte nicht den Experten fragen",
    "ask the expert not",
    "kein Experte",
])
def test_negated_expert_requests_do_not_escalate(text):
    assert policy.is_explicit_expert_request(text) is False


@pytest.mark.parametrize("text", [
    "Frag den Experten",
    "Frag den Experten bitte",
    "Hol den Experten dazu",
    "ask the expert about this",
    "Kannst du mal den Experten fragen? Frag mal den Experten.",
])
def test_positive_expert_requests_still_escalate(text):
    assert policy.is_explicit_expert_request(text) is True


# ── delegate_to_expert availability ──────────────────────────────────

def test_delegate_tool_only_offered_with_delegator():
    from core import tool_registry as reg
    tool.set_expert_delegator(None)
    try:
        assert "delegate_to_expert" not in reg.ALWAYS_INCLUDED_TOOLS
        assert tool.SCHEMA not in reg.ALWAYS_INCLUDED_TOOLS.values()
        tool.set_expert_delegator(lambda req: "ok", available=lambda: False)
        assert "delegate_to_expert" not in reg.ALWAYS_INCLUDED_TOOLS
        tool.set_expert_delegator(lambda req: "ok", available=lambda: True)
        assert "delegate_to_expert" in reg.ALWAYS_INCLUDED_TOOLS
        assert tool.SCHEMA in reg.ALWAYS_INCLUDED_TOOLS.values()
        assert "web_search" in reg.ALWAYS_INCLUDED_TOOLS
    finally:
        tool.set_expert_delegator(None)
