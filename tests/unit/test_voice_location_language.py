"""Regressions for the configured home, guest context, and German voice prompt."""

from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from core.config import Config
from core.llm_router import LLMRouter, ToolCallRequest
from core.tools import get_weather


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


@pytest.fixture(autouse=True)
def _synthetic_home(monkeypatch):
    monkeypatch.setattr("core.config.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv(
        "JARVIS_HOME_ADDRESS",
        "Musterort, Landkreis Beispielstadt, Deutschland",
    )
    monkeypatch.setenv("JARVIS_HOME_LAT", "49.0")
    monkeypatch.setenv("JARVIS_HOME_LON", "9.0")


def test_primary_home_is_configured_place_not_regional_city(monkeypatch):
    config = Config(str(CONFIG_PATH))
    monkeypatch.setattr(get_weather, "_config", config)
    monkeypatch.setattr(get_weather, "_current_user_fn", lambda: "primary_user")
    lat, lon, label = get_weather._resolve_location(None)
    assert "Musterort" in label
    assert "Beispielstadt" not in label.split(",", 1)[0]
    assert (lat, lon) == (float(config.get("location.home_lat")), float(config.get("location.home_lon")))

    llm = LLMRouter.__new__(LLMRouter)
    llm.home_location = label
    prompt = llm._build_system_prompt()
    assert f"Der Heimatort des Benutzers ist {label}" in prompt
    assert "ausschließlich auf Deutsch" in prompt


def test_guest_gets_no_invented_home_or_friend(monkeypatch):
    config = Config(str(CONFIG_PATH))
    monkeypatch.setattr(get_weather, "_config", config)
    monkeypatch.setattr(get_weather, "_current_user_fn", lambda: "__guest__")
    assert "nennen Sie einen Ort" in get_weather._resolve_location(None)
    assert "nennen Sie einen Ort" in get_weather.handler({"query_type": "sunrise"})

    llm = LLMRouter.__new__(LLMRouter)
    llm.home_location = config.get("location.home_address")
    prompt = llm._build_system_prompt(guest_mode=True)
    assert "Musterort" not in prompt
    assert "Beispielstadt" not in prompt
    assert "friend" not in prompt.lower()
    assert "Deutsch" in prompt


def test_weather_period_uses_resolved_home(monkeypatch):
    config = Config(str(CONFIG_PATH))
    monkeypatch.setattr(get_weather, "_config", config)
    monkeypatch.setattr(get_weather, "_current_user_fn", lambda: "primary_user")
    captured = {}

    def forecast(lat, lon, city, is_home):
        captured.update(lat=lat, lon=lon, city=city, is_home=is_home)
        return "forecast"

    monkeypatch.setattr(get_weather, "_weather_forecast", forecast)
    monkeypatch.setattr("core.weather_db.parse_temporal_phrase", lambda phrase: None)
    assert get_weather.handler({"query_type": "period", "period": "unbekannt"}) == "forecast"
    assert captured["city"] == config.get("location.home_address")
    assert captured["is_home"] is True


def test_tool_synthesis_keeps_german_and_hides_home_from_guest(monkeypatch):
    class CapturedPrompt(BaseException):
        pass

    captured = {}

    def capture_post(url, json, **kwargs):
        captured["prompt"] = json["messages"][-1]["content"]
        raise CapturedPrompt()

    monkeypatch.setattr("core.llm_router.requests.post", capture_post)
    monkeypatch.setattr(
        "core.debug_logger.get_debug_logger",
        lambda: SimpleNamespace(_write=lambda *args, **kwargs: None,
                                log_llm_messages=lambda *args, **kwargs: None),
    )
    llm = LLMRouter.__new__(LLMRouter)
    llm.logger = SimpleNamespace(debug=lambda *args, **kwargs: None,
                                 error=lambda *args, **kwargs: None)
    llm._stream_cancel_event = threading.Event()
    llm.last_call_chain = []
    llm._tool_call_messages = [{"role": "system", "content": "Gast-Prompt"}]
    llm.home_location = "Musterort"
    llm.local_model_path = "model.gguf"
    llm.small_model_enabled = False
    llm.small_endpoint = None
    llm.local_endpoint = "http://localhost/llm"
    llm.temperature = 0.5
    llm.top_p = 0.9
    llm.top_k = 40
    call = ToolCallRequest("get_weather", {})

    with pytest.raises(CapturedPrompt):
        next(llm.continue_after_tool_call(call, "Wolken", guest_mode=True))
    assert "Musterort" not in captured["prompt"]
    assert "Antworte standardmäßig auf Deutsch" in captured["prompt"]

    with pytest.raises(CapturedPrompt):
        next(llm.continue_after_tool_call(call, "Wolken", guest_mode=False))
    assert "The user's home location is Musterort" in captured["prompt"]
