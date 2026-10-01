"""German model envelopes and deterministic tool errors; no network or audio."""

import asyncio
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock

import pytest

from core import persona
from core.llm_router import LLMRouter, ToolCallRequest
from core.mcp_client import MCPBridge


@pytest.fixture
def router(monkeypatch):
    r = LLMRouter.__new__(LLMRouter)
    r.logger = Mock()
    r.config = SimpleNamespace(get=lambda key, default=None: "en" if key == "llm.response_language" else default)
    r.home_location = None
    r.local_model_path = "synthetic.gguf"
    r.local_endpoint = "http://synthetic.invalid/v1/chat/completions"
    r.temperature, r.top_p, r.top_k = 0.5, 0.9, 40
    r.primary_provider = "gemma"
    r.tool_calling = True
    r.audio_direct = False
    r.small_model_enabled = False
    r.small_endpoint = None
    r._record_call = Mock()
    r.last_call_chain = []
    r.last_call_info = None
    r._primary_text_fallback_allowed = lambda: False
    r._privacy_gate = SimpleNamespace(allow=lambda cap: True)
    monkeypatch.setattr("core.debug_logger.get_debug_logger", lambda: Mock())
    return r


def response(content="Die Quelle meldet Erfolg."):
    line = "data: " + json.dumps({"choices": [{"delta": {"content": content}}]})
    return SimpleNamespace(
        status_code=200,
        raise_for_status=lambda: None,
        json=lambda: {"choices": [{"message": {"content": content}}]},
        iter_lines=lambda: iter([line.encode(), b"data: [DONE]"]),
        close=lambda: None,
    )


@pytest.mark.parametrize("path", ["chat", "tools", "continuation", "small_continuation"])
def test_actual_payload_keeps_central_language_rule_and_english_tool_data(router, monkeypatch, path):
    payloads = []
    monkeypatch.setattr("core.llm_router.requests.post", lambda *a, **kw: payloads.append(kw["json"]) or response())
    query = "Was bedeutet das?"
    foreign = "The external source reports success."
    original = [{"role": "system", "content": "Legacy tool rules"}, {"role": "user", "content": query}]
    if path == "chat":
        assert router.chat(query, max_tokens=64) == "Die Quelle meldet Erfolg."
    elif path == "tools":
        assert "".join(router.stream_with_tools(query, max_tokens=64)) == "Die Quelle meldet Erfolg."
    else:
        if path == "small_continuation":
            router.small_model_enabled = True
            router.small_endpoint = "http://synthetic.invalid/small"
            router.small_temperature = 0.4
        request = ToolCallRequest("web_search", {"query": query}, call_id="synthetic", messages=original)
        assert "".join(router.continue_after_tool_call(request, foreign, max_tokens=64)) == "Die Quelle meldet Erfolg."
        assert next(m for m in payloads[0]["messages"] if m["role"] == "tool")["content"] == foreign
        assert original[0]["content"] == "Legacy tool rules"
    assert len(payloads) == 1  # No translation pass.
    assert persona.OWNER_LANGUAGE_RULE in payloads[0]["messages"][0]["content"]
    assert "aktuelle" in persona.OWNER_LANGUAGE_RULE  # Explicit output-language requests remain supported.


def test_registry_error_is_german_and_does_not_leak_exception(monkeypatch):
    from core import tool_registry as registry

    monkeypatch.setattr(registry, "_REGISTRY_READY", True)
    monkeypatch.setattr(registry, "get_privacy_gate", lambda: SimpleNamespace(allow=lambda cap: False))

    def fail(args):
        raise RuntimeError("https://synthetic.invalid/?key=SECRET_SYNTHETIC")

    monkeypatch.setitem(registry.TOOL_HANDLERS, "synthetic_fail", fail)
    logger = Mock()
    monkeypatch.setattr(registry, "logger", logger)
    result = registry.execute_tool("synthetic_fail", {})
    assert result == "Fehler: Das Werkzeug 'synthetic_fail' konnte die Anfrage nicht ausführen."
    assert "SECRET_SYNTHETIC" not in result + str(logger.mock_calls)
    assert persona.OWNER_LANGUAGE_RULE in registry.build_tool_prompt_rules({"web_search"})


def test_mcp_timeout_is_german_and_still_cancels(monkeypatch):
    import core.mcp_client as module

    monkeypatch.setattr(module, "get_privacy_gate", lambda: SimpleNamespace(allow=lambda cap: True))
    bridge = MCPBridge()
    loop = asyncio.new_event_loop()
    bridge._loop = loop
    bridge._timeouts = {"tool_call": 0.02}
    started, cancelled = threading.Event(), threading.Event()

    def run():
        asyncio.set_event_loop(loop)
        loop.call_soon(started.set)
        loop.run_forever()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert started.wait(1)

    async def slow(*args):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    bridge._call_tool = slow
    try:
        result = bridge._make_sync_handler("synthetic", "read")({})
        assert "Fehler:" in result and "Zeitgrenze überschritten" in result
        assert cancelled.wait(1)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(1)
        loop.close()


def test_mcp_error_payload_is_not_a_user_response(monkeypatch):
    bridge = MCPBridge()
    bridge._sessions["synthetic"] = SimpleNamespace(
        call_tool=AsyncMock(
            return_value=SimpleNamespace(
                isError=True, content=[SimpleNamespace(text="English failure SECRET_SYNTHETIC")]
            )
        )
    )
    assert asyncio.run(bridge._call_tool("synthetic", "read", {})) == (
        "Fehler: Das MCP-Werkzeug 'read' konnte die Anfrage nicht ausführen."
    )
    bridge._sessions.clear()
    bridge._reconnect_server = AsyncMock(return_value=False)
    assert asyncio.run(bridge._call_tool("synthetic", "read", {})) == (
        "Fehler: Der MCP-Server 'synthetic' ist nicht erreichbar."
    )


def test_developer_confirmation_is_german_and_does_not_execute(monkeypatch):
    from core.tools import developer_tools as tool

    monkeypatch.setattr(tool, "_pending_command", None)
    monkeypatch.setattr(
        tool,
        "_get_safety",
        lambda: SimpleNamespace(classify_command=lambda command: ("confirmation", "This requires confirmation")),
    )
    execution = Mock(side_effect=AssertionError("No command execution during preview"))
    monkeypatch.setattr(tool, "_run_cmd", execution)
    result = tool._devtools_run_command({"command": "synthetic_command"})
    assert result == "Bestätigung erforderlich: `synthetic_command`. Soll ich den Befehl ausführen?"
    assert tool._pending_command[0] == "synthetic_command"
    execution.assert_not_called()


def test_enrollment_pose_tts_and_frame_failure_are_german(monkeypatch):
    from core.tools import enroll_face as tool

    monkeypatch.setattr(tool.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(tool, "_capture_frame", lambda: "Fehler: Kein Kamerabild.")
    monkeypatch.setattr(tool, "_play_sound", Mock(side_effect=AssertionError("No playback")))
    tts = SimpleNamespace(speak=Mock())
    detector = SimpleNamespace(
        _real_tts=tts,
        _enrollment_state={"expires": time.time() + 30, "phase": "glasses_on", "frames": [], "_listener": None},
    )
    text, complete = tool.handle_enrollment_ready(detector)
    assert [c.args[0] for c in tts.speak.call_args_list] == [
        "Schauen Sie gerade in die Kamera.",
        "Drehen Sie sich jetzt leicht nach links.",
        "Und leicht nach rechts.",
    ]
    assert "Brille" in text and "ich bin bereit" in text and not complete


@pytest.mark.parametrize(
    "name,args,fragment",
    [
        ("recall_memory", {}, "Gedächtnissystem"),
        ("find_files", {"action": "search"}, "erforderlich"),
        ("delegate_to_expert", {}, "erforderlich"),
        ("generate_image", {}, "Bildbeschreibung"),
        ("get_news", {}, "nicht verfügbar"),
    ],
)
def test_actual_tool_missing_dependency_or_arguments_is_german(monkeypatch, name, args, fragment):
    import importlib

    module = importlib.import_module("core.tools." + name)
    for dep in getattr(module, "DEPENDENCIES", {}).values():
        monkeypatch.setattr(module, dep, None)
    assert fragment in module.handler(args)


def test_empty_search_context_is_german():
    from core.web_research import format_search_results

    assert format_search_results([]).startswith("Keine Suchergebnisse gefunden.")


@pytest.mark.parametrize(
    "temp,expected", [(100, "heiß"), (90, "warm"), (75, "angenehm"), (55, "mild"), (40, "kühl"), (20, "kalt")]
)
def test_weather_skill_real_cached_formatter_is_german(temp, expected):
    from skills.system.weather.skill import WeatherSkill

    skill = WeatherSkill.__new__(WeatherSkill)
    skill.respond = lambda text: text
    text = skill._format_current_response(
        {"temp": temp, "feels_like": temp + 10, "weather_main": "Rain", "wind_speed": 25}
    )
    assert expected in text and "Es regnet gerade." in text
    assert "Meilen pro Stunde" in text


def test_weather_skill_cached_forecast_rain_sun_and_missing_key(monkeypatch):
    from datetime import date, timedelta
    from skills.system.weather.skill import WeatherSkill

    skill = WeatherSkill.__new__(WeatherSkill)
    skill.logger = Mock()
    skill.respond = lambda text: text
    skill.api_key = None
    skill.tts = SimpleNamespace(speak=Mock())
    tomorrow = date.today() + timedelta(days=1)
    row = {"date": tomorrow.isoformat(), "temp_high": 90, "temp_low": 60, "weather_main": "rain", "rain_chance": 85}
    assert "Morgen wird es warm" in skill._format_tomorrow_response(row)
    assert "Das ist die Vorhersage" in skill._format_forecast_response([row])
    assert "Prozent Regenwahrscheinlichkeit" in skill._format_period_response([row], tomorrow, tomorrow)
    assert "Regen" in skill._format_rain_response(row)
    skill._db = SimpleNamespace(get_sun_times=lambda day: {"sunrise": "06:30"})
    skill._last_user_text = "sunrise tomorrow"  # Existing English input remains accepted.
    assert "Sonnenaufgang morgen ist um 06:30" in skill.get_sunrise()
    monkeypatch.setattr("requests.get", Mock(side_effect=AssertionError("No network")))
    assert "derzeit nicht verfügbar" in skill._fetch_current_live()
    assert "derzeit nicht verfügbar" in skill._fetch_forecast_live()


@pytest.mark.parametrize(
    "method",
    [
        "get_uptime",
        "get_disk_space",
        "get_username",
        "get_hostname",
        "get_cpu_info",
        "get_memory_info",
        "get_all_drives",
        "get_gpu_info",
    ],
)
def test_system_info_skill_actual_error_handlers_are_german_and_private(monkeypatch, method):
    from skills.system.system_info.skill import SystemInfoSkill

    skill = SystemInfoSkill.__new__(SystemInfoSkill)
    skill.logger = Mock()
    skill.respond = lambda text: text

    def fail(*args, **kwargs):
        raise RuntimeError("https://synthetic.invalid/?key=SECRET_SYNTHETIC")

    monkeypatch.setattr("builtins.open", fail)
    monkeypatch.setattr("shutil.disk_usage", fail)
    monkeypatch.setattr("os.getenv", fail)
    monkeypatch.setattr("platform.node", fail)
    monkeypatch.setattr("subprocess.run", fail)
    result = getattr(skill, method)()
    assert "Ich konnte" in result or "Fehler" in result
    assert "SECRET_SYNTHETIC" not in result + str(skill.logger.mock_calls)


def test_system_info_skill_actual_cpu_success_keeps_technical_model(monkeypatch):
    import io
    from skills.system.system_info.skill import SystemInfoSkill

    skill = SystemInfoSkill.__new__(SystemInfoSkill)
    skill.logger = Mock()
    skill.respond = lambda text: text
    monkeypatch.setattr("builtins.open", lambda *a, **kw: io.StringIO("model name : Synthetic CPU (TM)\n"))
    monkeypatch.setattr("subprocess.check_output", lambda *a, **kw: "8")
    result = skill.get_cpu_info()
    assert "Ihr Prozessor ist ein Synthetic CPU" in result and "8 Kernen" in result


def test_weather_skill_existing_english_today_input_and_live_ack_are_preserved(monkeypatch):
    from skills.system.weather.skill import WeatherSkill

    skill = WeatherSkill.__new__(WeatherSkill)
    skill.logger = Mock()
    skill.respond = lambda text: text
    skill.tts = SimpleNamespace(speak=Mock())
    skill._db = SimpleNamespace(get_forecast=lambda **kwargs: [])
    skill._get_away_geo = lambda: None
    skill._check_non_local = lambda: "OK"
    skill._last_user_text = "will it rain today"
    skill._fetch_rain_live = lambda: "Keine Wetterdaten verfügbar."
    skill._fetch_forecast_live = lambda: "Keine Wetterdaten verfügbar."
    assert skill._rain_check_is_today()
    assert skill.check_rain_tomorrow() == "Keine Wetterdaten verfügbar."
    assert skill.get_forecast() == "Keine Wetterdaten verfügbar."
    assert [c.args[0] for c in skill.tts.speak.call_args_list] == [
        f"Ich prüfe die Vorhersage, {skill.honorific}.",
        f"Ich rufe die erweiterte Vorhersage ab, {skill.honorific}.",
    ]


def test_package_info_preserves_external_location_parser_and_german_envelope(monkeypatch):
    from core.tools import find_files

    def run(command, **kwargs):
        if isinstance(command, list) and command[:2] == ["pip", "show"]:
            return "Name: synthetic\nVersion: 1.2\nLocation: /synthetic/location"
        return ""

    monkeypatch.setattr(find_files, "_run", run)
    result = find_files._find_package_info("synthetic")
    assert "pip: installiert" in result
    assert "Version 1.2" in result
    assert "Installationsort: /synthetic/location" in result
