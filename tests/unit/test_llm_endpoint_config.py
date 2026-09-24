from core.llm_router import LLMRouter


class MinimalConfig:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_local_llm_endpoint_uses_runtime_config():
    endpoint = "http://127.0.0.1:9080/v1/chat/completions"
    router = LLMRouter(MinimalConfig({"llm.local.endpoint": endpoint, "llm.local.llama_completion": ""}))
    assert router.local_endpoint == endpoint


def test_local_llm_endpoint_keeps_legacy_default():
    router = LLMRouter(MinimalConfig({"llm.local.llama_completion": ""}))
    assert router.local_endpoint == "http://127.0.0.1:8080/v1/chat/completions"
