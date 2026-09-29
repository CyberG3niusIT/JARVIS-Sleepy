"""Cloud LLM provider selection must be explicit and fail closed."""

from types import SimpleNamespace

import pytest

from core.llm_router import LLMRouter
from core.claude_consultation import ClaudeConsultation


class _Config:
    def __init__(self, values=None, env=None):
        self.values = values or {}
        self.env = env or {}
        self.env_reads = []

    def get(self, key, default=None):
        return self.values.get(key, default)

    def get_env(self, name, default=None):
        self.env_reads.append(name)
        return self.env.get(name, default)


def _router(values=None, env=None, allowed=True):
    router = LLMRouter.__new__(LLMRouter)
    router.config = _Config(values, env)
    router.logger = SimpleNamespace(**{
        name: lambda *args, **kwargs: None
        for name in ("debug", "info", "warning", "error")
    })
    router._privacy_gate = SimpleNamespace(allow=lambda capability: allowed)
    router.api_call_count = 0
    router.last_call_info = None
    router.last_call_chain = []
    router._record_call = lambda info: setattr(router, "last_call_info", info)
    router._estimate_max_tokens = lambda message: 50
    router._build_system_prompt = lambda guest_mode=False: "system"
    return router


def _cloud_values(provider="openrouter", **overrides):
    values = {
        "llm.api.enabled": True,
        "llm.api.provider": provider,
        "llm.api.model": "test/model",
        "llm.api.api_key_env": "OPENROUTER_API_KEY",
        "llm.api.endpoint": "https://cloud.invalid/v1/chat/completions",
        "llm.primary.text_fallback": True,
    }
    values.update(overrides)
    return values


def test_missing_provider_is_unconfigured_and_never_looks_up_anthropic(monkeypatch):
    router = _router({"llm.api.enabled": True}, {"ANTHROPIC_API_KEY": "secret"})
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("unexpected cloud call"))
    assert router._generate_api_chat("hello") == ""
    assert router.config.env_reads == []


def test_openrouter_uses_configured_endpoint_and_never_imports_anthropic(monkeypatch):
    router = _router(_cloud_values(), {"OPENROUTER_API_KEY": "secret"})
    seen = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "answer"}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2}}

    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr("requests.post", post)
    monkeypatch.setitem(__import__("sys").modules, "anthropic", None)
    assert router._generate_api_chat("hello") == "answer"
    assert seen["url"] == "https://cloud.invalid/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer secret"
    assert seen["json"]["messages"][0] == {"role": "system", "content": "system"}


def test_openrouter_never_reads_anthropic_credential_name(monkeypatch):
    values = _cloud_values(**{"llm.api.api_key_env": "ANTHROPIC_API_KEY"})
    router = _router(values, {"ANTHROPIC_API_KEY": "secret"})
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("unexpected cloud call"))

    assert router._generate_api_chat("hello") == ""
    assert router.config.env_reads == []


@pytest.mark.parametrize("credential_name", ["OPENAI_API_KEY", "CLOUD_TEST_KEY", "ANTHROPIC_API_KEY"])
def test_openrouter_rejects_credentials_owned_by_another_provider(monkeypatch, credential_name):
    values = _cloud_values(**{"llm.api.api_key_env": credential_name})
    router = _router(values, {credential_name: "secret"})
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("wrong credential must not be sent"))

    assert router._generate_api_chat("hello") == ""
    assert router.config.env_reads == []


def test_anthropic_provider_rejects_openrouter_credential_name(monkeypatch):
    router = _router(_cloud_values("anthropic"), {"OPENROUTER_API_KEY": "secret"})
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("wrong provider path"))
    monkeypatch.setitem(__import__("sys").modules, "anthropic", None)

    assert router._generate_api_chat("hello") == ""
    assert router.config.env_reads == []


def test_local_inference_error_uses_configured_openrouter_fallback(monkeypatch):
    router = _router(_cloud_values(), {"OPENROUTER_API_KEY": "secret"})
    router.fallback_enabled = True
    router._build_chat_prompt = lambda *args, **kwargs: "prompt"
    router._generate_local = lambda *args, **kwargs: ""
    router._check_response_quality = lambda *args, **kwargs: "low_quality"

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "cloud answer"}}]}

    seen = []
    monkeypatch.setattr("requests.post", lambda url, **kwargs: seen.append(url) or Response())
    assert router.chat("hello") == "cloud answer"
    assert seen == ["https://cloud.invalid/v1/chat/completions"]


def test_chat_respects_explicitly_disabled_primary_cloud_fallback(monkeypatch):
    router = _router(_cloud_values(**{"llm.primary.text_fallback": False}),
                     {"OPENROUTER_API_KEY": "secret"})
    router.fallback_enabled = True
    router._generate_local = lambda *args, **kwargs: "best local attempt"
    router._check_response_quality = lambda *args, **kwargs: "low_quality"
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("cloud fallback must stay disabled"))

    assert router.chat("hello") == "best local attempt"
    assert router.config.env_reads == []


def test_anthropic_path_requires_explicit_provider(monkeypatch):
    router = _router(_cloud_values("anthropic", **{"llm.api.api_key_env": "ANTHROPIC_API_KEY"}),
                     {"ANTHROPIC_API_KEY": "secret"})
    calls = []
    fake = SimpleNamespace(Anthropic=lambda **kwargs: SimpleNamespace(messages=SimpleNamespace(
        create=lambda **request: calls.append((kwargs, request)) or SimpleNamespace(
            content=[SimpleNamespace(text="answer")],
            usage=SimpleNamespace(input_tokens=1, output_tokens=2),
        )
    )))
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("wrong provider path"))
    assert router._generate_api_chat("hello") == "answer"
    assert calls and calls[0][1]["model"] == "test/model"


def test_cloud_disabled_skips_provider(monkeypatch):
    router = _router(_cloud_values(**{"llm.api.enabled": False}),
                     {"OPENROUTER_API_KEY": "secret"})
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("unexpected cloud call"))
    assert router._generate_api_chat("hello") == ""
    assert router.config.env_reads == []


def test_primary_fallback_flag_can_disable_cloud_fallback(monkeypatch):
    router = _router(_cloud_values(**{"llm.primary.text_fallback": False}),
                     {"OPENROUTER_API_KEY": "secret"})
    router.fallback_enabled = True
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("unexpected cloud call"))
    assert router._primary_text_fallback_allowed() is False


def test_primary_fallback_privacy_denial_precedes_credential_lookup():
    router = _router(_cloud_values(), {"OPENROUTER_API_KEY": "secret"}, allowed=False)
    router.fallback_enabled = True

    assert router._primary_text_fallback_allowed() is False
    assert router.config.env_reads == []


def test_privacy_gate_blocks_cloud_before_credentials_or_request(monkeypatch):
    router = _router(_cloud_values(), {"OPENROUTER_API_KEY": "secret"}, allowed=False)
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("unexpected cloud call"))
    assert router._generate_api_chat("hello") == ""
    assert router.config.env_reads == []


def test_missing_credentials_fail_without_switching_provider(monkeypatch):
    router = _router(_cloud_values(), {})
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("unexpected cloud call"))
    assert router._generate_api_chat("hello") == ""
    assert router.config.env_reads == ["OPENROUTER_API_KEY"]


def test_consultation_requires_explicit_anthropic_provider_before_key_lookup(monkeypatch):
    config = _Config({"llm.api.enabled": True, "llm.api.provider": "openrouter",
                      "llm.api.api_key_env": "OPENROUTER_API_KEY",
                      "llm.api.model": "test/model"},
                     {"OPENROUTER_API_KEY": "secret"})
    consultation = ClaudeConsultation.__new__(ClaudeConsultation)
    consultation.config = config
    consultation.api_key_env = "OPENROUTER_API_KEY"
    consultation.model = "test/model"
    consultation._privacy_gate = SimpleNamespace(allow=lambda capability: True)
    monkeypatch.setitem(__import__("sys").modules, "anthropic", None)
    with pytest.raises(PermissionError, match="Optional consultation is not configured"):
        consultation._call_claude("finding")
    assert config.env_reads == []


def test_consultation_rejects_openrouter_credential_name_before_key_lookup(monkeypatch):
    config = _Config({"llm.api.enabled": True, "llm.api.provider": "anthropic",
                      "llm.api.api_key_env": "OPENROUTER_API_KEY",
                      "llm.api.model": "test/model"},
                     {"OPENROUTER_API_KEY": "secret"})
    consultation = ClaudeConsultation.__new__(ClaudeConsultation)
    consultation.config = config
    consultation.api_key_env = "OPENROUTER_API_KEY"
    consultation.model = "test/model"
    consultation._privacy_gate = SimpleNamespace(allow=lambda capability: True)
    monkeypatch.setitem(__import__("sys").modules, "anthropic", None)

    with pytest.raises(PermissionError, match="Optional consultation is not configured"):
        consultation._call_claude("finding")
    assert config.env_reads == []


@pytest.mark.parametrize("values", [
    {"llm.primary.text_fallback": True,
     "llm.api.enabled": True,
     "llm.api.api_key_env": "ANTHROPIC_API_KEY"},
    {"llm.primary.text_fallback": True,
     "llm.api.enabled": False,
     "llm.api.provider": "openrouter",
     "llm.api.model": "test/model",
     "llm.api.endpoint": "https://cloud.invalid/v1/chat/completions",
     "llm.api.api_key_env": "OPENROUTER_API_KEY"},
    {"llm.primary.text_fallback": True,
     "llm.api.enabled": True,
     "llm.api.provider": "openrouter",
     "llm.api.model": "test/model",
     "llm.api.endpoint": "https://cloud.invalid/v1/chat/completions",
     "llm.api.api_key_env": "ANTHROPIC_API_KEY"},
])
def test_pipeline_does_not_probe_credentials_when_provider_is_not_runnable(values):
    from core.pipeline import Coordinator

    pipeline = Coordinator.__new__(Coordinator)
    pipeline.config = _Config(values)
    assert pipeline._text_fallback_available() is False
    assert pipeline.config.env_reads == []


def test_pipeline_text_fallback_respects_privacy_gate_before_credential_lookup():
    from core.pipeline import Coordinator

    pipeline = Coordinator.__new__(Coordinator)
    pipeline.config = _Config(_cloud_values(**{"llm.primary.text_fallback": True}),
                              {"OPENROUTER_API_KEY": "secret"})
    pipeline._privacy_gate = SimpleNamespace(allow=lambda capability: False)

    assert pipeline._text_fallback_available() is False
    assert pipeline.config.env_reads == []


def test_pipeline_text_fallback_uses_explicit_provider_and_privacy_gate():
    from core.pipeline import Coordinator

    pipeline = Coordinator.__new__(Coordinator)
    pipeline.config = _Config(_cloud_values(**{"llm.primary.text_fallback": True}),
                              {"OPENROUTER_API_KEY": "secret"})
    pipeline._privacy_gate = SimpleNamespace(allow=lambda capability: True)

    assert pipeline._text_fallback_available() is True
    assert pipeline.config.env_reads == ["OPENROUTER_API_KEY"]


def test_metrics_classify_configured_cloud_providers_without_breaking_legacy_fields(tmp_path):
    import time
    from core.metrics_tracker import MetricsTracker

    tracker = MetricsTracker(_Config({"metrics.db_path": str(tmp_path / "metrics.db")}))
    now = time.time()
    for provider in ("gemma", "openrouter", "anthropic", "claude"):
        tracker.record(timestamp=now, provider=provider, method="chat")

    rows = tracker.get_timeseries(hours=1)
    assert len(rows) == 1
    assert rows[0]["local_model_count"] == 1
    assert rows[0]["cloud_count"] == 3
    assert rows[0]["claude_count"] == 1
