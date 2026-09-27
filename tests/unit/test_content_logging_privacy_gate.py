"""Unit tests for session #8 agentic-audit finding #3: several
content-bearing logger.debug/.info call sites logged raw user content
(tool-call arguments, search/routing query text, image-generation
prompts) via the plain file logger, completely outside the
CONTENT_LOGGING PrivacyGate gate that other call sites in the same
codebase already respect (core/skill_manager.py, core/conversation.py,
core/debug_logger.py). tool_registry.py's own instance of this bug
(execute_tool()'s `logger.debug("execute_tool: %s(%s)", ...)`) is
covered separately in test_tool_registry_audit_privacy.py.

Fixed here:
  - core/llm_router.py: _log_tool_call() (used by both call sites in
    stream_with_tools()) — tool-call arguments.
  - core/tool_gate.py: should_include_tools() classifier-skip branch —
    up to 80 chars of raw query text.
  - core/tools/generate_image.py: handler() — the image-generation
    prompt.

Real PrivacyGate throughout (singleton reset around every test), no
mocking of the gate itself — only of loggers/network calls that are
irrelevant to what's being verified.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import logging as _logging

import pytest

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


class TestLLMRouterLogToolCallHelper:
    """core/llm_router.py's _log_tool_call() — extracted from
    stream_with_tools() so the gating logic is directly testable
    without driving the whole SSE-streaming generator."""

    def _get(self):
        from core.llm_router import _log_tool_call
        return _log_tool_call

    def test_args_absent_from_log_during_privacy(self, caplog):
        log_tool_call = self._get()
        gate = get_privacy_gate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        logger = _logging.getLogger("test.llm_router.privacy")

        with caplog.at_level("INFO", logger="test.llm_router.privacy"):
            log_tool_call(logger, gate, "Tool call", "run_command",
                          {"command": "rm -rf /home/user/secret-project"})

        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert "run_command" in joined  # tool name (metadata) still logged
        assert "secret-project" not in joined  # argument content suppressed

    def test_args_present_in_log_outside_privacy(self, caplog):
        log_tool_call = self._get()
        gate = get_privacy_gate()
        logger = _logging.getLogger("test.llm_router.normal")

        with caplog.at_level("INFO", logger="test.llm_router.normal"):
            log_tool_call(logger, gate, "Tool call", "run_command",
                          {"command": "ls -la"})

        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert "run_command" in joined
        assert "ls -la" in joined


class TestToolGateQueryLoggingGated:
    def test_classifier_skip_log_omits_query_during_privacy(self, monkeypatch, caplog):
        import core.tool_gate as tool_gate

        class _FakeClf:
            def predict_proba(self, emb):
                return [[0.99, 0.01]]  # prob_tool = 0.01, well under threshold

        monkeypatch.setattr(tool_gate, "_load_classifier", lambda: _FakeClf())

        get_privacy_gate().enter(PrivacyMode.PRIVACY, actor="test")

        with caplog.at_level("INFO", logger="jarvis.tool_gate"):
            result = tool_gate.should_include_tools(
                "what's my bank account balance and routing number",
                embedding=[0.1, 0.2, 0.3],
            )

        assert result is False
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert "routing number" not in joined

    def test_classifier_skip_log_includes_query_outside_privacy(self, monkeypatch, caplog):
        import core.tool_gate as tool_gate

        class _FakeClf:
            def predict_proba(self, emb):
                return [[0.99, 0.01]]

        monkeypatch.setattr(tool_gate, "_load_classifier", lambda: _FakeClf())

        with caplog.at_level("INFO", logger="jarvis.tool_gate"):
            result = tool_gate.should_include_tools(
                "tell me a joke about penguins",
                embedding=[0.1, 0.2, 0.3],
            )

        assert result is False
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert "penguins" in joined


class TestGenerateImagePromptLoggingGated:
    class _FakeSwap:
        def swap_to(self, target):
            return True

        def swap_back(self):
            return True

    class _FakeResponse:
        status_code = 500
        headers = {"content-type": "text/plain"}
        text = "simulated failure — no real network call made"

    def test_prompt_absent_from_log_during_privacy(self, monkeypatch, caplog):
        import core.tools.generate_image as gen_img

        monkeypatch.setattr(gen_img, "get_gpu_swap_manager", lambda: self._FakeSwap())
        monkeypatch.setattr(gen_img.requests, "post", lambda *a, **k: self._FakeResponse())
        get_privacy_gate().enter(PrivacyMode.PRIVACY, actor="test")

        with caplog.at_level("INFO", logger="jarvis.tools.generate_image"):
            gen_img.handler({"prompt": "a portrait of my daughter Lena at her birthday party"})

        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert "Lena" not in joined

    def test_prompt_present_in_log_outside_privacy(self, monkeypatch, caplog):
        import core.tools.generate_image as gen_img

        monkeypatch.setattr(gen_img, "get_gpu_swap_manager", lambda: self._FakeSwap())
        monkeypatch.setattr(gen_img.requests, "post", lambda *a, **k: self._FakeResponse())

        with caplog.at_level("INFO", logger="jarvis.tools.generate_image"):
            gen_img.handler({"prompt": "a red sports car on a mountain road"})

        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert "red sports car" in joined
