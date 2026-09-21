"""Unit tests for session #7's privacy gap fix in core/tool_registry.py's
execute_tool(): its structured tool_execution/tool_completed event
(persisted to the event_logger SQLite DB) previously ran unconditionally
regardless of privacy mode — found as a byproduct of adding equivalent
audit logging to skill_manager.execute_intent() (see
test_skill_audit_logging.py) and checking whether the existing
tool_registry pattern had the same gap. It did.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

import core.tool_registry as tool_registry
from core.privacy_gate import (
    PrivacyMode,
    get_privacy_gate,
    reset_privacy_gate_singleton_for_tests,
)


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_privacy_gate_singleton_for_tests()
    yield
    reset_privacy_gate_singleton_for_tests()


@pytest.fixture
def registry_ready(monkeypatch):
    monkeypatch.setattr(tool_registry, "_REGISTRY_READY", True)
    monkeypatch.setattr(tool_registry, "TOOL_HANDLERS", {"echo_tool": lambda args: "hello"})
    yield


class _FakeEventLogger:
    def __init__(self):
        self.calls = []

    def emit(self, **kwargs):
        self.calls.append(kwargs)


class TestExecuteToolAuditGatedByPrivacy:
    def test_no_event_emitted_during_privacy(self, registry_ready, monkeypatch):
        fake_el = _FakeEventLogger()
        monkeypatch.setattr("core.event_logger.get_event_logger", lambda *a, **k: fake_el)

        get_privacy_gate().enter(PrivacyMode.PRIVACY, actor="test")

        result = tool_registry.execute_tool("echo_tool", {"text": "geheim"})

        assert result == "hello"  # tool still executes — only the audit log is gated
        assert fake_el.calls == []

    def test_event_emitted_outside_privacy(self, registry_ready, monkeypatch):
        fake_el = _FakeEventLogger()
        monkeypatch.setattr("core.event_logger.get_event_logger", lambda *a, **k: fake_el)

        result = tool_registry.execute_tool("echo_tool", {"text": "normal"})

        assert result == "hello"
        assert len(fake_el.calls) == 1
        assert fake_el.calls[0]["metadata"]["tool_name"] == "echo_tool"

    def test_error_path_also_gated_during_privacy(self, monkeypatch):
        def boom(args):
            raise RuntimeError("tool exploded")

        monkeypatch.setattr(tool_registry, "_REGISTRY_READY", True)
        monkeypatch.setattr(tool_registry, "TOOL_HANDLERS", {"broken_tool": boom})

        fake_el = _FakeEventLogger()
        monkeypatch.setattr("core.event_logger.get_event_logger", lambda *a, **k: fake_el)

        get_privacy_gate().enter(PrivacyMode.PRIVACY, actor="test")

        result = tool_registry.execute_tool("broken_tool", {})

        assert "Error executing broken_tool" in result
        assert fake_el.calls == []
