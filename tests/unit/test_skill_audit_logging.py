"""Unit tests for session #7 agentic-audit finding #6: skill_manager's
execute_intent() had ZERO structured audit logging — tool_registry's
execute_tool() (LLM function-calling path) already emitted
tool_execution/tool_completed events, but most voice commands are
routed via execute_intent()'s pattern/keyword/semantic matching, not
LLM tool calls, so "what did JARVIS do autonomously" reconstruction
from the event DB missed the majority of actual command execution.

Also covers the related privacy gap found as a byproduct: neither
skill_manager's new audit event nor tool_registry's existing one
respected PrivacyGate — both now skip emission entirely (not just
redact) during privacy, consistent with every other content-logging
call site gated this session.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.skill_manager import SkillManager
from core.privacy_gate import (
    Capability,
    PrivacyMode,
    get_privacy_gate,
    reset_privacy_gate_singleton_for_tests,
)


class _NullLogger:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_privacy_gate_singleton_for_tests()
    yield
    reset_privacy_gate_singleton_for_tests()


@pytest.fixture
def manager():
    mgr = SkillManager.__new__(SkillManager)
    mgr.logger = _NullLogger()
    mgr._privacy_gate = get_privacy_gate()
    return mgr


class TestSkillAuditEventEmitted:
    def test_emits_event_on_success(self, manager, monkeypatch):
        captured = []

        class _FakeEventLogger:
            def emit(self, **kwargs):
                captured.append(kwargs)

        monkeypatch.setattr(
            "core.event_logger.get_event_logger",
            lambda *a, **k: _FakeEventLogger(),
        )

        import time
        manager._emit_skill_audit_event(
            "weather", "get_forecast", {"original_text": "wie wird das wetter"},
            time.time(), "Es wird sonnig, Sir.",
        )

        assert len(captured) == 1
        assert captured[0]["metadata"]["skill_name"] == "weather"
        assert captured[0]["metadata"]["pattern"] == "get_forecast"
        assert captured[0]["status"] == "success"

    def test_metadata_never_includes_entity_values_or_response_text(self, manager, monkeypatch):
        """Stricter than tool_registry's existing pattern: only entity
        KEY NAMES and response LENGTH, never values/content."""
        captured = []

        class _FakeEventLogger:
            def emit(self, **kwargs):
                captured.append(kwargs)

        monkeypatch.setattr(
            "core.event_logger.get_event_logger",
            lambda *a, **k: _FakeEventLogger(),
        )

        import time
        secret_response = "Ihr Passwort lautet geheim123"
        manager._emit_skill_audit_event(
            "file_editor", "read_file",
            {"original_text": "geheime Anfrage über meine Kontodaten", "path": "/home/alex/secret.txt"},
            time.time(), secret_response,
        )

        meta = captured[0]["metadata"]
        assert meta["entity_keys"] == ["original_text", "path"]  # keys only
        assert "geheime" not in str(meta)
        assert "secret.txt" not in str(meta)
        assert "Passwort" not in str(meta)
        assert meta["response_length"] == len(secret_response)

    def test_emits_event_on_error(self, manager, monkeypatch):
        captured = []

        class _FakeEventLogger:
            def emit(self, **kwargs):
                captured.append(kwargs)

        monkeypatch.setattr(
            "core.event_logger.get_event_logger",
            lambda *a, **k: _FakeEventLogger(),
        )

        import time
        manager._emit_skill_audit_event(
            "developer_tools", "run_command", {"original_text": "..."},
            time.time(), None, error=RuntimeError("boom"),
        )

        assert captured[0]["status"] == "error"
        assert "boom" in captured[0]["metadata"]["error"]

    def test_never_raises_if_event_logger_unavailable(self, manager, monkeypatch):
        monkeypatch.setattr(
            "core.event_logger.get_event_logger",
            lambda *a, **k: None,
        )
        import time
        manager._emit_skill_audit_event("weather", "get_forecast", {}, time.time(), "ok")  # must not raise

    def test_never_raises_if_event_logger_explodes(self, manager, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("event logger exploded")
        monkeypatch.setattr("core.event_logger.get_event_logger", boom)
        import time
        manager._emit_skill_audit_event("weather", "get_forecast", {}, time.time(), "ok")  # must not raise


class TestSkillAuditEventGatedByPrivacy:
    def test_no_emission_during_privacy(self, manager, monkeypatch):
        captured = []

        class _FakeEventLogger:
            def emit(self, **kwargs):
                captured.append(kwargs)

        monkeypatch.setattr(
            "core.event_logger.get_event_logger",
            lambda *a, **k: _FakeEventLogger(),
        )

        manager._privacy_gate.enter(PrivacyMode.PRIVACY, actor="test")

        import time
        manager._emit_skill_audit_event(
            "file_editor", "read_file", {"original_text": "geheim"}, time.time(), "response",
        )

        assert captured == []

    def test_emission_resumes_after_exit(self, manager, monkeypatch):
        captured = []

        class _FakeEventLogger:
            def emit(self, **kwargs):
                captured.append(kwargs)

        monkeypatch.setattr(
            "core.event_logger.get_event_logger",
            lambda *a, **k: _FakeEventLogger(),
        )

        manager._privacy_gate.enter(PrivacyMode.PRIVACY, actor="test")
        manager._privacy_gate.exit(actor="test")

        import time
        manager._emit_skill_audit_event("weather", "get_forecast", {}, time.time(), "ok")

        assert len(captured) == 1
