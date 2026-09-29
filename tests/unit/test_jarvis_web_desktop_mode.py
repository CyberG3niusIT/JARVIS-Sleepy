"""jarvis_web.py --desktop-mode: read-only, loopback-only; the default mode is unchanged."""

from types import SimpleNamespace
import asyncio
import json

from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer
import pytest


def _app(tmp_path, monkeypatch, *, desktop_mode):
    import core.tool_registry
    import jarvis_web

    monkeypatch.setattr(core.tool_registry, "get_images_dir", lambda: str(tmp_path / "tool-images"))
    config = SimpleNamespace(
        get=lambda key, default=None: str(tmp_path / "flux") if key == "image_generation.output_dir" else default
    )
    app = jarvis_web.create_app(config, desktop_mode=desktop_mode)
    app["config"] = config
    app["auth_token"] = ""
    return app


def _run(app, scenario):
    async def go():
        async with TestClient(TestServer(app)) as client:
            return await scenario(client)

    return asyncio.run(go())


MUTATING = [
    ("POST", "/api/upload"),
    ("POST", "/api/upload-image"),
    ("POST", "/api/generate-image"),
    ("PUT", "/api/session/1/rename"),
    ("PATCH", "/api/memory/facts/abc"),
    ("DELETE", "/api/memory/facts/abc"),
    ("DELETE", "/api/memory/interactions/1"),
    ("POST", "/api/governance/proposals/1/review"),
    ("POST", "/api/governance/proposals/1/confirm"),
    ("POST", "/api/governance/circuit-breaker/reset"),
    ("POST", "/api/governance/test-proposal"),
    ("POST", "/api/observations/collect"),
    ("POST", "/api/observations/consult"),
]


def test_desktop_mode_refuses_every_mutating_route_with_403(tmp_path, monkeypatch):
    import jarvis_web
    app = _app(tmp_path, monkeypatch, desktop_mode=True)

    async def scenario(client):
        results = {}
        for method, path in MUTATING:
            response = await client.request(method, path, data=b"{}")
            results[(method, path)] = (response.status, await response.json())
        return results

    for key, (status, body) in _run(app, scenario).items():
        assert status == 403, key
        assert body == {"error": jarvis_web.DESKTOP_MODE_REJECTION, "desktopMode": True}, key


def test_desktop_mode_keeps_get_routes_reachable(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, desktop_mode=True)

    async def scenario(client):
        stats = await client.get("/api/stats")
        head = await client.head("/api/stats")
        return stats.status, head.status

    # 503 = "components not initialised" from the real handler: the middleware let the GET through.
    assert _run(app, scenario) == (503, 503)


def test_default_mode_does_not_install_the_read_only_middleware(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, desktop_mode=False)
    assert app["desktop_mode"] is False

    async def scenario(client):
        response = await client.post("/api/generate-image", data=b"not json")
        return response.status

    assert _run(app, scenario) == 400  # the real handler answered (invalid JSON), not the desktop guard


def test_desktop_mode_middleware_logs_the_rejection(tmp_path, monkeypatch, caplog):
    app = _app(tmp_path, monkeypatch, desktop_mode=True)

    async def scenario(client):
        await client.delete("/api/memory/facts/abc")

    with caplog.at_level("WARNING", logger="jarvis.web"):
        _run(app, scenario)
    assert any("DELETE /api/memory/facts/abc" in record.getMessage() for record in caplog.records)


def test_desktop_mode_websocket_accepts_only_client_info(tmp_path, monkeypatch, caplog):
    """Second layer: the socket handler itself. The read middleware already refuses /ws in desktop
    mode, so this app has the flag but not the middleware to exercise the handler in isolation."""
    import jarvis_web
    app = _app(tmp_path, monkeypatch, desktop_mode=False)
    app["desktop_mode"] = True
    app["components"] = {
        "doc_buffer": object(),
        "conversation": SimpleNamespace(load_full_history=lambda: [], current_user="u"),
    }
    app["tts_proxy"] = SimpleNamespace(get_pending_announcements=lambda: [])
    app["ws_connections"] = {}

    async def first_error(ws, payload):
        await ws.send_json(payload)
        async with asyncio.timeout(5):
            while True:
                message = await ws.receive()
                if message.type != WSMsgType.TEXT:
                    return None
                data = message.json()
                if data.get("type") == "error":
                    return data

    async def scenario(client):
        async with client.ws_connect("/ws") as ws:
            rejected = {}
            for kind in ("message", "slash_command", "toggle_voice", "set_user", "client_location", "file_drop"):
                rejected[kind] = await first_error(ws, {"type": kind, "content": "hi", "command": "/x", "enabled": True})
            await ws.send_json({"type": "client_info", "client_id": "test", "user_agent": "test", "screen_width": 1920})
            await ws.close()
            return rejected

    with caplog.at_level("WARNING", logger="jarvis.web"):
        rejected = _run(app, scenario)
    assert all(data == {"type": "error", "content": jarvis_web.DESKTOP_MODE_REJECTION} for data in rejected.values())
    assert sum("WebSocket-Nachricht" in record.getMessage() for record in caplog.records) == 6
    assert jarvis_web._DESKTOP_WS_ALLOWED_TYPES == frozenset({"client_info"})


@pytest.mark.parametrize("kwargs,expected", [
    ({}, None),
    ({"host": "127.0.0.1", "port": 8091}, None),
    ({"voice": True}, "--voice"),
    ({"host": "0.0.0.0"}, "127.0.0.1"),
    ({"host": "192.168.0.5"}, "127.0.0.1"),
    ({"port": 8443}, "8091"),
    ({"port": 9000}, "8091"),
])
def test_desktop_mode_arguments_cannot_widen_the_binding(kwargs, expected):
    import jarvis_web
    args = SimpleNamespace(**{"voice": False, "host": None, "port": None, **kwargs})
    problem = jarvis_web._desktop_mode_argument_problem(args)
    assert (problem is None) if expected is None else (expected in problem)


def test_desktop_mode_is_loopback_8091_only():
    import jarvis_web
    assert (jarvis_web.DESKTOP_MODE_HOST, jarvis_web.DESKTOP_MODE_PORT) == ("127.0.0.1", 8091)


@pytest.mark.parametrize("configured,expected", [
    ("${JARVIS_WEB_AUTH_TOKEN}", ""), ("", ""), (None, ""), ("local-test-token", "local-test-token"),
])
def test_desktop_mode_token_honors_a_real_token_and_ignores_placeholders(configured, expected):
    import jarvis_web
    config = SimpleNamespace(get=lambda key, default=None: configured if key == "web.auth_token" else default)
    assert jarvis_web._desktop_mode_auth_token(config) == expected


def test_desktop_mode_never_needs_the_https_token_rule(tmp_path):
    """The default path raises when TLS certs exist without a token; desktop mode has no TLS at all."""
    import jarvis_web
    cert, key = tmp_path / "tls.crt", tmp_path / "tls.key"
    cert.touch()
    key.touch()
    values = {"web.auth_token": "", "web.tls": {"enabled": True, "cert": str(cert), "key": str(key)}}
    config = SimpleNamespace(get=lambda name, default=None: values.get(name, default))
    with pytest.raises(RuntimeError):
        jarvis_web._configured_web_auth_token(config)
    assert jarvis_web._desktop_mode_auth_token(config) == ""


# --- GET allowlist ---------------------------------------------------------------------------

# Copy of what the WinUI app really requests (BackendHub -> JarvisApiClient). The C# harness
# UI/tests/WinUiBackendAdapters.Tests asserts the app never requests anything outside this list.
WINUI_READ_REQUESTS = [
    "/api/stats",
    "/api/desktop/snapshot",
    "/api/agents/status",
    "/api/automations/status",
    "/api/memory/summary",
    "/api/events/recent?hours=24&limit=40",
    "/api/events/aggregate?hours=24",
    "/api/sessions?limit=1",
    "/api/webcam/status",
]

FORBIDDEN_READS = [
    "/", "/index.html", "/memory", "/dashboard", "/dashboard/health", "/dashboard/pipeline",
    "/dashboard/governance", "/ws", "/ws/dashboard",
    "/api/webcam/stream", "/api/webcam/snapshot", "/api/browse?path=/tmp",
    "/api/history", "/api/session/1", "/api/desktop/live", "/api/metrics/summary",
    "/api/metrics/export", "/api/events/stt", "/api/events/tts", "/api/events/speaker_id",
    "/api/events/routing", "/api/events/watchdog", "/api/events/health", "/api/gpu-status",
    "/api/governance/status", "/api/governance/proposals", "/api/observations/findings",
    "/api/memory/facts", "/api/memory/interactions", "/api/memory/timeseries", "/api/memory/db-health",
    "/images/x.png", "/generated/x.png", "/app.js", "/nope",
    # allowed path, key outside the allowlist
    "/api/sessions?limit=1&user=someone", "/api/events/recent?hours=1&category=voice",
    "/api/stats?verbose=1",
]


@pytest.mark.parametrize("target", WINUI_READ_REQUESTS)
def test_desktop_mode_lets_the_winui_read_endpoints_through(tmp_path, monkeypatch, target):
    app = _app(tmp_path, monkeypatch, desktop_mode=True)

    async def scenario(client):
        return (await client.get(target)).status, (await client.head(target)).status

    # The real handlers answer 503 ("components not initialised") here; anything but 403 = let through.
    statuses = _run(app, scenario)
    assert 403 not in statuses, (target, statuses)


@pytest.mark.parametrize("target", FORBIDDEN_READS)
def test_desktop_mode_refuses_every_other_read_with_403_for_get_and_head(tmp_path, monkeypatch, target):
    import jarvis_web
    app = _app(tmp_path, monkeypatch, desktop_mode=True)

    async def scenario(client):
        response = await client.get(target)
        body = await response.json()
        return response.status, body, (await client.head(target)).status

    status, body, head_status = _run(app, scenario)
    assert (status, head_status) == (403, 403), target
    assert body == {"error": jarvis_web.DESKTOP_MODE_REJECTION, "desktopMode": True}


def test_desktop_mode_allowlist_covers_every_registered_get_route_decision(tmp_path, monkeypatch):
    """Completeness: every GET route the app registers is either allowlisted or answers 403."""
    import jarvis_web
    app = _app(tmp_path, monkeypatch, desktop_mode=True)
    placeholders = {"{session_id}": "1", "{id}": "1", "{fact_id}": "1", "{interaction_id}": "1"}
    paths = set()
    for resource in app.router.resources():
        if not any(route.method in ("GET", "*") for route in resource):
            continue
        info = resource.get_info()
        if "prefix" in info:  # static directory: probe a file below it
            paths.add(info["prefix"].rstrip("/") + "/x.png")
            continue
        path = info.get("path") or info.get("formatter") or ""
        for name, value in placeholders.items():
            path = path.replace(name, value)
        paths.add(path)

    async def scenario(client):
        return {path: (await client.get(path)).status for path in paths}

    results = _run(app, scenario)
    allowed = set(jarvis_web._DESKTOP_READ_ALLOWLIST)
    assert allowed <= paths
    for path, status in results.items():
        assert (status != 403) == (path in allowed), (path, status)


def test_desktop_mode_tolerates_the_auth_token_query_key(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, desktop_mode=True)

    async def scenario(client):
        return (await client.get("/api/stats?token=abc")).status

    assert _run(app, scenario) != 403


def test_desktop_mode_read_rejections_are_logged_without_the_query(tmp_path, monkeypatch, caplog):
    app = _app(tmp_path, monkeypatch, desktop_mode=True)

    async def scenario(client):
        await client.get("/api/webcam/stream?token=SECRET_TOKEN_VALUE")

    with caplog.at_level("WARNING", logger="jarvis.web"):
        _run(app, scenario)
    messages = [record.getMessage() for record in caplog.records]
    assert any("GET /api/webcam/stream abgelehnt" in message for message in messages)
    assert not any("SECRET_TOKEN_VALUE" in message for message in messages)


def test_desktop_mode_refuses_both_websocket_endpoints_at_http_level(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, desktop_mode=True)

    async def scenario(client):
        headers = {"Connection": "Upgrade", "Upgrade": "websocket",
                   "Sec-WebSocket-Version": "13", "Sec-WebSocket-Key": "x" * 22 + "=="}
        return [(await client.get(path, headers=headers)).status for path in ("/ws", "/ws/dashboard")]

    assert _run(app, scenario) == [403, 403]


def test_default_mode_keeps_all_read_routes_open(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, desktop_mode=False)

    async def scenario(client):
        targets = ["/api/webcam/status", "/api/history", "/api/browse?path=/tmp", "/api/desktop/live"]
        return {target: (await client.get(target)).status for target in targets}

    assert 403 not in _run(app, scenario).values()


# --- honest ownership semantics --------------------------------------------------------------

def _request(desktop_mode, components):
    return SimpleNamespace(app={"components": components, "desktop_mode": desktop_mode})


def test_desktop_automations_never_claim_disabled_for_workers_it_does_not_own():
    import jarvis_web
    response = asyncio.run(jarvis_web.automations_status_handler(_request(True, {})))
    schedulers = {item["id"]: item for item in json.loads(response.text)["schedulers"]}
    assert schedulers["reminder_poller"]["state"] == "backend_owned"
    assert schedulers["reminder_poller"]["owner"] == "voice-daemon"
    assert schedulers["health_snapshot"]["state"] == "backend_owned"
    assert schedulers["health_snapshot"]["owner"] == "voice-daemon"
    assert schedulers["observation_collector"]["state"] == "unavailable"
    assert schedulers["observation_collector"]["owner"] == "web-standard-mode"
    assert not any(item["state"] in ("disabled", "stopped", "running") for item in schedulers.values())


def test_desktop_automations_do_not_report_a_local_running_state_as_system_state():
    import jarvis_web

    class Thread:
        def is_alive(self):
            return True

    class Reminder:
        _running = True
        _poll_thread = Thread()
        poll_interval = 30

    response = asyncio.run(jarvis_web.automations_status_handler(_request(True, {"reminder_manager": Reminder()})))
    reminder = next(item for item in json.loads(response.text)["schedulers"] if item["id"] == "reminder_poller")
    assert reminder["state"] == "backend_owned" and reminder["configuredIntervalSeconds"] == 30


def test_default_automations_semantics_are_unchanged():
    import jarvis_web
    response = asyncio.run(jarvis_web.automations_status_handler(_request(False, {})))
    payload = json.loads(response.text)
    assert [item["state"] for item in payload["schedulers"]] == ["disabled", "disabled", "disabled"]
    assert all("owner" not in item for item in payload["schedulers"])


def test_desktop_agents_status_is_backend_owned_not_a_local_idle():
    import jarvis_web

    class Planner:
        active_plan = None
        has_pending_confirmation = False
        is_paused = False
        can_pause = False

    response = asyncio.run(jarvis_web.agents_status_handler(_request(True, {"task_planner": Planner()})))
    payload = json.loads(response.text)
    assert response.status == 200
    assert payload["available"] is False and payload["state"] == "backend_owned"
    default = asyncio.run(jarvis_web.agents_status_handler(_request(False, {"task_planner": Planner()})))
    assert json.loads(default.text)["state"] == "idle" and json.loads(default.text)["available"] is True


def test_desktop_snapshot_reports_unowned_workers_as_unknown_not_not_loaded():
    import jarvis_web
    config = SimpleNamespace(get=lambda key, default=None: default)
    components = {"calendar_manager": None, "news_manager": None, "weather_poller": None,
                  "memory_manager": object()}
    desktop = jarvis_web._desktop_snapshot(config, components, True)["capabilities"]
    default = jarvis_web._desktop_snapshot(config, components)["capabilities"]
    assert (desktop["calendar"], desktop["news"], desktop["weather"]) == (None, None, None)
    assert desktop["memory"] is True
    assert (default["calendar"], default["news"], default["weather"]) == (False, False, False)
