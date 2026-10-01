"""Nonstream primary chat uses the same structured template contract as stream."""

from types import SimpleNamespace

import pytest

from core.llm_router import LLMRouter


@pytest.fixture
def router(monkeypatch):
    router = LLMRouter.__new__(LLMRouter)
    router.logger = SimpleNamespace(**{name: lambda *a, **kw: None
                                       for name in ("debug", "info", "warning", "error")})
    router.last_call_info = None
    router._build_system_prompt = lambda guest_mode=False: "guest" if guest_mode else "system"
    router._primary_text_fallback_allowed = lambda: False
    router.resolve_role = lambda role: {
        "model_name": "local", "provider": "gemma", "endpoint": "http://localhost/v1/chat/completions",
        "temperature": .5, "top_p": .9, "enable_thinking": False,
    }
    router._record_call = lambda info: setattr(router, "last_call_info", info)
    router.strip_filler = lambda text: text
    router._check_response_quality = lambda text, query: None if text else "empty"
    return router


def capture_requests(monkeypatch, responses):
    bodies = []

    def post(url, *, json, timeout):
        bodies.append(json)
        content = next(responses)
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                               json=lambda: {"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr("core.llm_router.requests.post", post)
    return bodies


def test_primary_chat_has_single_system_current_user_and_thinking_contract(router, monkeypatch):
    bodies = capture_requests(monkeypatch, iter(["Bereit."]))
    assert router.chat("Bereit?", max_tokens=32, memory_context="Kontext", guest_mode=True) == "Bereit."
    assert len(bodies) == 1
    assert bodies[0]["messages"] == [
        {"role": "system", "content": "guest\n\nKontext"},
        {"role": "user", "content": "Bereit?"},
    ]
    assert bodies[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert router.last_call_info["method"] == "chat"


@pytest.mark.parametrize("structured", [False, True])
def test_primary_chat_preserves_history_and_appends_current_turn(router, monkeypatch, structured):
    bodies = capture_requests(monkeypatch, iter(["Antwort."]))
    history = [{"role": "user", "content": "Vorher"}, {"role": "assistant", "content": "Antwort"}]
    kwargs = {"conversation_messages": history} if structured else {
        "conversation_history": "USER: Vorher\nASSISTANT: Antwort"}
    router.chat("Jetzt", max_tokens=32, **kwargs)
    assert bodies[0]["messages"][1:] == history + [{"role": "user", "content": "Jetzt"}]
    assert len(history) == 2  # Caller-owned history is not mutated.


def test_primary_chat_does_not_drop_user_when_assistant_has_same_content(router, monkeypatch):
    bodies = capture_requests(monkeypatch, iter(["Antwort."]))
    router.chat("Jetzt", max_tokens=32, conversation_messages=[{"role": "assistant", "content": "Jetzt"}])
    assert bodies[0]["messages"][-1] == {"role": "user", "content": "Jetzt"}


def test_primary_chat_does_not_duplicate_current_user(router, monkeypatch):
    bodies = capture_requests(monkeypatch, iter(["Antwort."]))
    router.chat("Jetzt", max_tokens=32, conversation_messages=[{"role": "user", "content": "Jetzt"}])
    assert bodies[0]["messages"][1:] == [{"role": "user", "content": "Jetzt"}]


def test_primary_chat_empty_retry_uses_structured_german_nudge(router, monkeypatch):
    bodies = capture_requests(monkeypatch, iter(["", "Antwort."]))
    assert router.chat("Jetzt", max_tokens=32) == "Antwort."
    assert len(bodies) == 2
    assert all("<|im_start|>" not in message["content"]
               for body in bodies for message in body["messages"])
    assert bodies[1]["messages"][-1]["content"].startswith("Jetzt\n\nBitte")
    assert router.last_call_info["quality_gate"] is True


def test_empty_local_attempts_remain_empty_when_cloud_is_disallowed(router, monkeypatch):
    bodies = capture_requests(monkeypatch, iter(["", ""]))
    router._generate_api_chat = lambda *args, **kwargs: pytest.fail("cloud must remain disabled")
    assert router.chat("Jetzt", max_tokens=32) == ""
    assert len(bodies) == 2


def test_generate_remains_plain_user_compatible(router, monkeypatch):
    bodies = capture_requests(monkeypatch, iter(["Antwort."]))
    assert router._generate_local("Frage", 32) == "Antwort."
    assert bodies[0]["messages"][-1] == {"role": "user", "content": "Frage"}


@pytest.mark.parametrize("error, expected", [
    ({"message": "PRIVATE_SYNTHETIC_PROMPT"}, "bad_request"),
    ("PRIVATE_SYNTHETIC_PROMPT", "bad_request"),
    ({"type": "exceed_context_size_error", "n_prompt_tokens": "PRIVATE_SYNTHETIC_PROMPT",
      "n_ctx": "PRIVATE_SYNTHETIC_PROMPT"}, "context_overflow"),
])
def test_server_errors_do_not_persist_response_content(router, monkeypatch, error, expected):
    logs = []
    router.logger.error = lambda message, *args: logs.append(message % args if args else message)
    monkeypatch.setattr("core.llm_router.requests.post", lambda *a, **kw:
                        SimpleNamespace(status_code=400, json=lambda: {"error": error}))
    assert router._generate_local("synthetic", 32) == ""
    assert router.last_call_info["error"] == expected
    assert "PRIVATE_SYNTHETIC_PROMPT" not in str(logs) + str(router.last_call_info)


def test_transport_error_does_not_persist_url_or_prompt(router, monkeypatch):
    logs = []
    router.logger.error = lambda message, *args: logs.append(message % args if args else message)

    def fail(*args, **kwargs):
        raise RuntimeError("https://synthetic.invalid/?key=PRIVATE_SYNTHETIC_SECRET")

    monkeypatch.setattr("core.llm_router.requests.post", fail)
    assert router._generate_local("synthetic", 32) == ""
    assert router.last_call_info["error"] == "RuntimeError"
    assert "PRIVATE_SYNTHETIC_SECRET" not in str(logs) + str(router.last_call_info)


def test_success_usage_cannot_persist_provider_content(router, monkeypatch):
    monkeypatch.setattr("core.llm_router.requests.post", lambda *a, **kw:
                        SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                                        json=lambda: {"choices": [{"message": {"content": "Antwort."}}],
                                                      "usage": {"prompt_tokens": "PRIVATE_SYNTHETIC_PROMPT",
                                                                "completion_tokens": -1}}))
    assert router._generate_local("synthetic", 32) == "Antwort."
    assert router.last_call_info["input_tokens"] is None
    assert router.last_call_info["output_tokens"] is None
    assert "PRIVATE_SYNTHETIC_PROMPT" not in str(router.last_call_info)


def test_malformed_success_records_only_failure(router, monkeypatch):
    records = []
    router._record_call = records.append
    monkeypatch.setattr("core.llm_router.requests.post", lambda *a, **kw:
                        SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                                        json=lambda: {"choices": [{"message": {"content": None}}]}))
    assert router._generate_local("synthetic", 32) == ""
    assert len(records) == 1
    assert records[0]["error"] == "ValueError"
