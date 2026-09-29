from scripts import check_runtime_dependencies as runtime


class ConfigStub:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def _base_config(tmp_path, **overrides):
    model_dir = tmp_path / "stt-model"
    model_dir.mkdir(parents=True, exist_ok=True)
    values = {
        "llm.local.endpoint": "http://127.0.0.1:8080/v1/chat/completions",
        "stt.backend": "qwen3",
        "stt.qwen3.model_dir": str(model_dir),
        "llm.small.enabled": False,
        "mobility.enabled": False,
    }
    values.update(overrides)
    return ConfigStub(values)


def test_required_local_llm_and_stt_are_checked(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "_get_json", lambda url, timeout=2.0: (200, {"status": "ok"}))
    failures, degraded = runtime.check(_base_config(tmp_path))
    assert failures == []
    assert degraded == []


def test_non_loopback_llm_endpoint_fails_required_check(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "_get_json", lambda url, timeout=2.0: (200, {"status": "ok"}))
    failures, _ = runtime.check(_base_config(tmp_path, **{
        "llm.local.endpoint": "http://remote.example/v1/chat/completions",
    }))
    assert failures == ["LLM /health nicht bereit (endpoint is not loopback HTTP)."]


def test_loopback_llm_url_with_userinfo_is_rejected_without_request(monkeypatch, tmp_path):
    requested = []
    monkeypatch.setattr(runtime, "_get_json", lambda url, timeout=2.0: requested.append(url))
    failures, _ = runtime.check(_base_config(tmp_path, **{
        "llm.local.endpoint": "http://user:secret@127.0.0.1:8080/v1/chat/completions",
    }))
    assert failures == ["LLM /health nicht bereit (endpoint is not loopback HTTP)."]
    assert requested == []


def test_loopback_llm_url_with_query_or_fragment_is_rejected(monkeypatch, tmp_path):
    requested = []
    monkeypatch.setattr(runtime, "_get_json", lambda url, timeout=2.0: requested.append(url))
    for suffix in ("?token=secret", "#health"):
        failures, _ = runtime.check(_base_config(tmp_path, **{
            "llm.local.endpoint": f"http://127.0.0.1:8080/v1/chat/completions{suffix}",
        }))
        assert failures == ["LLM /health nicht bereit (endpoint is not loopback HTTP)."]
    assert requested == []


def test_missing_vvs_configuration_is_degraded_not_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "_get_json", lambda url, timeout=2.0: (200, {"status": "ok", "ready": True}))
    failures, degraded = runtime.check(_base_config(tmp_path, **{
        "mobility.enabled": True,
        "mobility.base_url": "${WIMAEDV_VVS_BASE_URL}",
    }))
    assert failures == []
    assert any("VVS-URL ist nicht konfiguriert" in item for item in degraded)


def test_unready_vvs_is_degraded(monkeypatch, tmp_path):
    def get_json(url, timeout=2.0):
        if url.endswith("/ready"):
            return 200, {"ready": False}
        return 200, {"status": "ok"}

    monkeypatch.setattr(runtime, "_get_json", get_json)
    failures, degraded = runtime.check(_base_config(tmp_path, **{
        "mobility.enabled": True,
        "mobility.base_url": "http://127.0.0.1:8088",
    }))
    assert failures == []
    assert any("VVS /health oder /ready" in item for item in degraded)


def test_vvs_health_without_optional_status_accepts_positive_ready(monkeypatch, tmp_path):
    def get_json(url, timeout=2.0):
        if ":8080/" in url:
            return 200, {"status": "ok"}
        if url.endswith("/ready"):
            return 200, {"ready": True}
        return 200, {}

    monkeypatch.setattr(runtime, "_get_json", get_json)
    failures, degraded = runtime.check(_base_config(tmp_path, **{
        "mobility.enabled": True,
        "mobility.base_url": "http://127.0.0.1:8088",
    }))
    assert failures == []
    assert degraded == []


def test_vvs_negative_health_status_is_degraded_even_if_ready(monkeypatch, tmp_path):
    def get_json(url, timeout=2.0):
        if ":8080/" in url:
            return 200, {"status": "ok"}
        if url.endswith("/ready"):
            return 200, {"ready": True}
        return 200, {"status": "starting"}

    monkeypatch.setattr(runtime, "_get_json", get_json)
    failures, degraded = runtime.check(_base_config(tmp_path, **{
        "mobility.enabled": True,
        "mobility.base_url": "http://127.0.0.1:8088",
    }))
    assert failures == []
    assert any("VVS /health oder /ready" in item for item in degraded)


def test_vvs_ok_false_is_degraded_even_if_ready(monkeypatch, tmp_path):
    def get_json(url, timeout=2.0):
        if ":8080/" in url:
            return 200, {"status": "ok"}
        if url.endswith("/ready"):
            return 200, {"ready": True}
        return 200, {"ok": False}

    monkeypatch.setattr(runtime, "_get_json", get_json)
    failures, degraded = runtime.check(_base_config(tmp_path, **{
        "mobility.enabled": True,
        "mobility.base_url": "http://127.0.0.1:8088",
    }))
    assert failures == []
    assert any("VVS /health oder /ready" in item for item in degraded)


def test_vvs_urls_with_userinfo_query_or_fragment_are_not_requested(monkeypatch, tmp_path):
    requested = []

    def get_json(url, timeout=2.0):
        requested.append(url)
        return 200, {"status": "ok"}

    monkeypatch.setattr(runtime, "_get_json", get_json)
    unsafe_urls = (
        "http://user:secret@127.0.0.1:8088",
        "http://127.0.0.1:8088?token=secret",
        "http://127.0.0.1:8088#health",
        "http://127.0.0.1:8088?",
        "http://127.0.0.1:8088#",
    )
    for url in unsafe_urls:
        failures, degraded = runtime.check(_base_config(tmp_path, **{
            "mobility.enabled": True,
            "mobility.base_url": url,
        }))
        assert failures == []
        assert any("VVS /health oder /ready" in item for item in degraded)
    assert not any(":8088" in url for url in requested)


def test_small_llm_non_loopback_endpoint_is_not_requested(monkeypatch, tmp_path, capsys):
    requested = []

    def get_json(url, timeout=2.0):
        requested.append(url)
        return 200, {"status": "ok"}

    monkeypatch.setattr(runtime, "_get_json", get_json)
    failures, degraded = runtime.check(_base_config(tmp_path, **{
        "llm.small.enabled": True,
        "llm.small.endpoint": "http://remote.example/v1/chat/completions",
    }))
    assert failures == []
    assert degraded == []   # optional and absent: informational only, never DEGRADED
    assert "INFO: Optionales Small-LLM ist nicht erreichbar" in capsys.readouterr().out
    assert all("remote.example" not in url for url in requested)


def test_missing_stt_model_is_a_required_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "_get_json", lambda url, timeout=2.0: (200, {"status": "ok"}))
    failures, _ = runtime.check(_base_config(tmp_path, **{
        "stt.qwen3.model_dir": str(tmp_path / "missing-model"),
    }))
    assert failures == ["Konfiguriertes STT-Modell fehlt."]


def test_primary_unit_comes_from_handover_config_even_when_handover_disabled(monkeypatch):
    monkeypatch.delenv("JARVIS_LLM_UNIT", raising=False)
    config = ConfigStub({"handover.enabled": False, "handover.units.primary": "llama-server-primary.service"})
    assert runtime.primary_unit(config) == "llama-server-primary.service"


def test_primary_unit_precedence_env_then_llm_primary_then_handover(monkeypatch):
    config = ConfigStub({"llm.primary.unit": "a-primary.service", "handover.units.primary": "b-primary.service"})
    monkeypatch.delenv("JARVIS_LLM_UNIT", raising=False)
    assert runtime.primary_unit(config) == "a-primary.service"
    monkeypatch.setenv("JARVIS_LLM_UNIT", "env-primary.service")
    assert runtime.primary_unit(config) == "env-primary.service"


def test_legacy_unit_is_only_the_explicit_fallback(monkeypatch):
    monkeypatch.delenv("JARVIS_LLM_UNIT", raising=False)
    assert runtime.primary_unit(ConfigStub({})) == runtime.LEGACY_LLM_UNIT
    assert runtime.expert_unit(ConfigStub({})) is None


def test_invalid_unit_names_are_ignored(monkeypatch):
    monkeypatch.delenv("JARVIS_LLM_UNIT", raising=False)
    config = ConfigStub({"llm.primary.unit": "evil; rm -rf /.service", "handover.units.primary": "ok.service",
                         "handover.units.expert": "../x"})
    assert runtime.primary_unit(config) == "ok.service"
    assert runtime.expert_unit(config) is None


def test_real_config_resolves_gemma_primary_and_expert_units(monkeypatch):
    from core.config import Config
    monkeypatch.delenv("JARVIS_LLM_UNIT", raising=False)
    config = Config()
    assert runtime.primary_unit(config) == "llama-server-primary.service"
    assert runtime.expert_unit(config) == "llama-server-expert.service"


def test_llm_start_wait_follows_the_handover_timeout_and_is_capped(tmp_path):
    assert runtime.llm_start_wait(_base_config(tmp_path)) == 180                       # default
    assert runtime.llm_start_wait(_base_config(tmp_path, **{"handover.primary_start_timeout_s": 240})) == 240
    assert runtime.llm_start_wait(_base_config(tmp_path, **{"handover.primary_start_timeout_s": 900})) == 300
    assert runtime.llm_start_wait(_base_config(tmp_path, **{"handover.primary_start_timeout_s": "x"})) == 180


def test_primary_endpoint_helpers_replace_the_hardcoded_port():
    from core import runtime_state
    cfg = ConfigStub({"llm.primary.endpoint": "http://127.0.0.1:9191/v1/chat/completions"})
    assert runtime_state.primary_endpoint(cfg) == "http://127.0.0.1:9191/v1/chat/completions"
    assert runtime_state.primary_base_url(cfg) == "http://127.0.0.1:9191"
    assert runtime_state.primary_base_url(ConfigStub({})) == "http://127.0.0.1:8080"
    assert runtime_state.primary_base_url(None) == "http://127.0.0.1:8080"
    assert runtime.primary_endpoint(cfg) == runtime_state.primary_endpoint(cfg)


def test_health_check_and_preflight_report_a_handover_as_swapping(tmp_path, monkeypatch):
    from core import health_check, runtime_state
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path))
    runtime_state.write_handover({"state": "STOPPING_PRIMARY", "is_swapping": True})
    calls = []

    def fake_run(command, timeout=10):
        calls.append(command)
        if "is-active" in command:
            return True, "active"
        if "curl" in command:
            return False, ""
        return True, "0"

    monkeypatch.setattr(health_check, "_run", fake_run)
    monkeypatch.setattr(health_check.time, "sleep", lambda s: None)
    cfg = ConfigStub({"llm.primary.endpoint": "http://127.0.0.1:9191/v1/chat/completions"})
    llama = [c for c in health_check.check_services(cfg) if c["name"] == "llama-server"][0]
    assert llama["status"] == "yellow" and "Swapping" in llama["summary"]     # not "red"/down
    assert any("127.0.0.1:9191/health" in c for c in calls)                     # config endpoint, not :8080
    assert len([c for c in calls if "curl" in c]) == 1                          # no 24 s retry loop during a swap
