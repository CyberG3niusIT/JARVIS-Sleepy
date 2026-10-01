"""Auth regression on real routes, with inert API handlers and temporary data."""
import asyncio
from types import SimpleNamespace

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest


def app_for(tmp_path, monkeypatch, desktop=False):
    import jarvis_web
    import core.tool_registry
    monkeypatch.setattr(core.tool_registry, "get_images_dir", lambda: str(tmp_path / "images"))
    config = SimpleNamespace(get=lambda k, d=None: str(tmp_path / "generated")
                             if k == "image_generation.output_dir" else d)
    seen = []
    async def inert(request):
        seen.append(request.path)
        return web.json_response({"test": True})
    monkeypatch.setattr(jarvis_web, "session_messages_handler", inert)
    monkeypatch.setattr(jarvis_web, "stats_overview_handler", inert)
    monkeypatch.setattr(jarvis_web, "memory_fact_delete_handler", inert)
    app = jarvis_web.create_app(config, desktop_mode=desktop)
    app["auth_token"] = "isolated-test-token"
    return app, seen


def get(app, path, token=False, method="GET"):
    async def run():
        async with TestClient(TestServer(app)) as client:
            headers = {"Authorization": "Bearer isolated-test-token"} if token else {}
            async with client.request(method, path, headers=headers) as response:
                await response.read()
                return response.status
    return asyncio.run(run())


@pytest.mark.parametrize("suffix", ["", ".js", ".css", ".png", ".jpg", ".svg", ".woff2"])
def test_dynamic_api_path_requires_auth_even_with_static_suffix(tmp_path, monkeypatch, suffix):
    app, seen = app_for(tmp_path, monkeypatch)
    assert get(app, "/api/session/item" + suffix) == 401
    assert seen == []


def test_authenticated_suffixed_api_still_reaches_handler(tmp_path, monkeypatch):
    app, seen = app_for(tmp_path, monkeypatch)
    assert get(app, "/api/session/item.js", token=True) == 200
    assert seen == ["/api/session/item.js"]


@pytest.mark.parametrize("suffix", [".js", ".png"])
def test_suffixed_write_handler_is_never_public(tmp_path, monkeypatch, suffix):
    app, seen = app_for(tmp_path, monkeypatch)
    assert get(app, "/api/memory/facts/item" + suffix, method="DELETE") == 401
    assert seen == []


@pytest.mark.parametrize("path", ["/api/missing.js", "/ws/missing.png"])
def test_static_catchall_cannot_make_api_or_ws_namespaces_public(tmp_path, monkeypatch, path):
    app, seen = app_for(tmp_path, monkeypatch)
    assert get(app, path) == 401
    assert seen == []


@pytest.mark.parametrize("prefix", ["images", "generated"])
def test_registered_image_static_resources_remain_public(tmp_path, monkeypatch, prefix):
    app, _ = app_for(tmp_path, monkeypatch)
    (tmp_path / prefix / "test.png").write_bytes(b"isolated-image-placeholder")
    assert get(app, "/" + prefix + "/test.png") == 200


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_real_public_static_asset_remains_public(tmp_path, monkeypatch, method):
    app, _ = app_for(tmp_path, monkeypatch)
    assert get(app, "/dashboard_mail.js", method=method) == 200


def test_websocket_stays_authenticated(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    assert get(app, "/ws") == 401


def test_static_html_page_is_not_made_public(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    assert get(app, "/dashboard_mail.html") == 401


@pytest.mark.parametrize("path", ["/api/session/item.js", "/api/session/item.png", "/dashboard_mail.js", "/ws"])
def test_desktop_does_not_widen_allowlist(tmp_path, monkeypatch, path):
    app, seen = app_for(tmp_path, monkeypatch, desktop=True)
    assert get(app, path, token=True) == 403
    assert seen == []


@pytest.mark.parametrize("token,expected", [(False, 401), (True, 200)])
def test_desktop_allowed_read_respects_auth(tmp_path, monkeypatch, token, expected):
    app, seen = app_for(tmp_path, monkeypatch, desktop=True)
    assert get(app, "/api/stats", token=token) == expected
    assert bool(seen) is token
