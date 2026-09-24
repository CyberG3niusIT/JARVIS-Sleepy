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


def test_small_llm_non_loopback_endpoint_is_not_requested(monkeypatch, tmp_path):
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
    assert any("Optionales Small-LLM ist nicht erreichbar" in item for item in degraded)
    assert all("remote.example" not in url for url in requested)


def test_missing_stt_model_is_a_required_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "_get_json", lambda url, timeout=2.0: (200, {"status": "ok"}))
    failures, _ = runtime.check(_base_config(tmp_path, **{
        "stt.qwen3.model_dir": str(tmp_path / "missing-model"),
    }))
    assert failures == ["Konfiguriertes STT-Modell fehlt."]
