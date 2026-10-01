"""Exercise real Web/Console handlers without runtime, devices or model calls."""

import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import web
from core import persona

ROOT = Path(__file__).resolve().parents[2]


def load_function(filename, name, **namespace):
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    scope = {"persona": persona, "logger": Mock(), "web": web, "Path": Path, **namespace}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / filename), "exec"), scope)
    return scope[name]


def test_web_browser_without_source_is_german():
    handler = load_function("jarvis_web.py", "_open_in_browser", _get_cached_content=lambda state: ("", None))
    response, _ = asyncio.run(handler(None, SimpleNamespace(), None, {}))
    assert "Keine URL" in response


def test_web_browser_failure_has_german_frame_without_exception_leak():
    handler = load_function(
        "jarvis_web.py",
        "_open_in_browser",
        _get_cached_content=lambda state: ("", {"result_urls": [{"url": "https://example.invalid"}]}),
    )
    with patch("subprocess.Popen", side_effect=OSError("private foreign error")):
        response, _ = asyncio.run(handler(None, SimpleNamespace(), None, {}))
    assert "Browser" in response and "nicht öffnen" in response
    assert "private foreign error" not in response


@pytest.mark.parametrize("name", ["sessions_handler", "session_messages_handler", "history_handler"])
def test_web_uninitialized_error_is_german(name):
    handler = load_function("jarvis_web.py", name)
    result = asyncio.run(handler(SimpleNamespace(app={})))
    assert result.status == 503
    assert json.loads(result.text)["error"] == "Nicht initialisiert"


@pytest.mark.parametrize(
    "command, expected",
    [
        ("/file", "Verwendung:"),
        ("/context", "Kein Dokument"),
        ("/clear", "leer"),
        ("/does-not-exist", "Unbekannter Befehl"),
    ],
)
def test_console_commands_have_german_feedback(command, expected):
    handler = load_function("jarvis_console.py", "_handle_slash_command")
    console = Mock()
    assert handler(command, SimpleNamespace(active=False), console, None)
    assert expected in console.print.call_args.args[0]


def test_console_search_keeps_german_rule_with_english_source(capsys):
    from core.llm_router import ToolCallRequest

    llm = SimpleNamespace(
        _build_system_prompt=lambda: persona.system_prompt(),
        continue_after_tool_call=lambda *a: iter(["Die Quelle nennt Python."]),
    )
    researcher = SimpleNamespace(
        search=lambda q: ["English source"], fetch_pages_parallel=lambda r: ["An English article"]
    )
    import sys

    handler = load_function(
        "jarvis_console.py",
        "_do_web_search",
        ToolCallRequest=ToolCallRequest,
        format_search_results=lambda r: "English source",
        sys=sys,
    )
    response = handler("Erkläre Python", researcher, llm, Mock())
    assert response == "Die Quelle nennt Python."
    system = llm._tool_call_messages[0]["content"]
    assert persona.OWNER_LANGUAGE_RULE in system
    assert "Suchergebnisse" in system
    assert llm._tool_call_messages[1]["content"] == "Erkläre Python"


@pytest.mark.parametrize(
    "command, expected",
    [
        ("/paste", "Kein Text"),
        ("/append", "Kein Text"),
        ("/context", "leer"),
        ("/file", "Verwendung:"),
        ("/help", "Werkzeugleiste"),
    ],
)
def test_web_slash_feedback_is_german(command, expected):
    from core.document_buffer import DocumentBuffer

    handler = load_function("jarvis_web.py", "_handle_ws_slash", DocumentBuffer=DocumentBuffer)
    ws = SimpleNamespace(send_json=AsyncMock())
    asyncio.run(handler(ws, command, {}, DocumentBuffer()))
    assert expected in ws.send_json.call_args.args[0]["content"]


def test_web_file_boundary_remains_closed_and_german(tmp_path):
    handler = load_function("jarvis_web.py", "_load_file_into_buffer", _is_path_allowed=lambda p: False)
    ws = SimpleNamespace(send_json=AsyncMock())
    asyncio.run(handler(ws, None, str(tmp_path / "private.txt")))
    assert ws.send_json.call_args.args[0]["content"] == "Zugriff verweigert: Pfad außerhalb der erlaubten Verzeichnisse"


def test_readback_foreign_source_has_german_frames():
    from core.readback_session import ReadbackSession

    session = ReadbackSession()
    assert session._build_from_json(
        {
            "source": "English Website",
            "sections": [
                {"type": "ingredients", "items": ["2 cups flour"]},
                {"type": "instructions", "steps": [{"step": 1, "text": "Mix carefully"}]},
            ],
        }
    )
    assert session.get_step(1) == "Schritt 1: Mix carefully"
    assert session.search_ingredients("flour") == "Das Rezept benötigt 2 cups flour."
    assert session.get_summary() == "Das war alles aus English Website: 1 Zutaten, 1 Schritte."
    assert session.chunks[0].title == "Zutaten"


def test_stream_readback_real_request_has_central_rule():
    import threading

    response = Mock()
    response.iter_lines.return_value = [
        b'data: {"choices":[{"delta":{"content":"Die Quelle lautet: hello."}}]}',
        b"data: [DONE]",
    ]
    ws = SimpleNamespace(send_json=AsyncMock())
    handler = load_function(
        "jarvis_web.py",
        "_stream_readback",
        asyncio=asyncio,
        threading=threading,
        _primary_chat_url=lambda: "http://localhost.invalid/chat",
    )
    llm = SimpleNamespace(temperature=0.3, top_p=0.9, top_k=40, strip_filler=lambda s: s)
    with patch("requests.post", return_value=response) as post:
        result, streamed = asyncio.run(
            handler(ws, llm, "An English article", current_request="Lies es bitte auf Englisch vor.")
        )
    assert streamed and result == "Die Quelle lautet: hello."
    payload = post.call_args.kwargs["json"]
    assert persona.OWNER_LANGUAGE_RULE in payload["messages"][0]["content"]
    assert "An English article" in payload["messages"][1]["content"]
    assert "Aktuelle Anfrage: Lies es bitte auf Englisch vor." in payload["messages"][1]["content"]
    assert post.call_count == 1


@pytest.mark.parametrize(
    "prefix", ["Fehler:", "Gesperrt:", "Bestätigung erforderlich:", "Error", "BLOCKED", "CONFIRMATION REQUIRED"]
)
def test_localized_transient_tool_results_never_enter_cache(prefix):
    from core.interaction_cache import store_tool_artifact

    cache = Mock()
    assert (
        store_tool_artifact(
            "developer_tools", {}, prefix + " Dieses Ergebnis darf nicht gespeichert werden.", cache, SimpleNamespace()
        )
        is None
    )
    cache.store.assert_not_called()


@pytest.mark.parametrize(
    "command, offer, expected",
    [
        ("ja", "Soll ich es vorlesen?", "read"),
        ("yes", "Soll ich es vorlesen?", "read"),
        ("yes", "Would you like me to read it?", "read"),
        ("ja bitte drucken", "Soll ich es vorlesen, anzeigen, drucken oder online öffnen?", "print"),
        ("zeige es mir im chat", "", "display"),
        ("open the page", "", "browse"),
        ("ja", "Soll ich den Befehl ausführen?", None),
        ("Java erklären", "Soll ich es vorlesen?", None),
        ("Januar Termine anzeigen", "Soll ich es vorlesen?", None),
        ("ja, drucken", "Soll ich es vorlesen?", "print"),
    ],
)
def test_delivery_keeps_german_and_english_input_compatibility(command, offer, expected):
    names = {
        "_AFFIRM_WORDS",
        "_DELIVERY_MODES",
        "_DELIVERY_CLARIFY",
        "_SHOW_ME_RESOLVERS",
        "_OFFER_PHRASES",
        "_CLARIFY_PHRASES",
    }
    tree = ast.parse((ROOT / "jarvis_web.py").read_text())
    constants = [
        n
        for n in tree.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)
    ]
    scope = {}
    exec(compile(ast.Module(body=constants, type_ignores=[]), "delivery_constants", "exec"), scope)
    handler = load_function("jarvis_web.py", "_detect_delivery_mode", **scope)
    assert handler(command, offer) == expected


@pytest.mark.parametrize("name", ["webcam_stream_handler", "webcam_snapshot_handler"])
def test_webcam_failure_is_german_without_provider_exception(name):
    import aiohttp

    handler = load_function(
        "jarvis_web.py", name, _aiohttp_lib=aiohttp, asyncio=asyncio, _WEBCAM_SERVER="http://example.invalid"
    )
    session = Mock()
    session.get.side_effect = aiohttp.ClientError("PRIVATE_FOREIGN_ERROR")
    response = asyncio.run(handler(SimpleNamespace(app={"http_session": session})))
    assert response.status == 503
    assert response.text == "Webcam nicht verfügbar"


def test_context_summary_real_request_has_german_rule_and_preserves_data():
    from core.privacy_gate import Capability

    tree = ast.parse((ROOT / "core/context_window.py").read_text())
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ContextWindow")
    node = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "_summarize_segment")
    import requests

    scope = {"TopicSegment": object, "Capability": Capability, "requests": requests}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "context_summary", "exec"), scope)
    subject = SimpleNamespace(_privacy_gate=SimpleNamespace(allow=lambda capability: True), config=None, logger=Mock())
    segment = SimpleNamespace(
        messages=[{"role": "user", "content": "English source text"}], summary="", segment_id=None, label="test"
    )
    response = Mock()
    response.json.return_value = {"choices": [{"message": {"content": "Deutsch zusammengefasst."}}]}
    with patch("requests.post", return_value=response) as post:
        scope["_summarize_segment"](subject, segment)
    messages = post.call_args.kwargs["json"]["messages"]
    assert persona.OWNER_LANGUAGE_RULE in messages[0]["content"]
    assert "English source text" in messages[1]["content"]
    assert segment.summary == "Deutsch zusammengefasst."
    assert post.call_count == 1


def test_normal_english_source_result_keeps_cache_behavior():
    from core.interaction_cache import store_tool_artifact

    cache = Mock()
    cache.ensure_window_id.return_value = "isolated-window"
    cache.store.return_value = "artifact-id"
    content = "An English source article describing the Python programming language."
    assert (
        store_tool_artifact(
            "developer_tools",
            {"action": "read_file", "path": "example.py"},
            content,
            cache,
            SimpleNamespace(turn_count=1),
        )
        == "artifact-id"
    )
    artifact = cache.store.call_args.args[0]
    assert artifact.content == content


def test_structured_readback_preserves_current_language_request_without_extra_call():
    from core.readback_session import ReadbackSession

    llm = Mock()
    llm.chat.return_value = json.dumps({"source": "Source", "sections": [{"type": "ingredients", "items": ["salt"]}]})
    session = ReadbackSession()
    assert session.parse_content(
        "English source", "previous German response", llm, current_request="Bitte diesmal auf Englisch."
    )
    assert llm.chat.call_count == 1
    prompt = llm.chat.call_args.args[0]
    assert persona.OWNER_LANGUAGE_RULE in prompt
    assert "Aktuelle Anfrage: Bitte diesmal auf Englisch." in prompt
