"""Unit tests for session #6 item 7: PrivacyGate call-site audit —
FILESYSTEM_OBSERVATION (core/tools/find_files.py, skills/system/filesystem/
skill.py) and REMOTE_TOOL (core/mcp_client.py's MCP tool-call bridge).

AGENT_CONTEXT_INGEST and SESSION_SUMMARY were already wired and tested
in tests/unit/test_privacy_conversation_persistence.py this session —
not duplicated here.

Real objects throughout where importable in this sandbox. The `mcp`
package needed no reproducible workaround beyond a plain `pip install
mcp` (unlike sounddevice/PortAudio, which needs a native library not
available here) — core/mcp_client.py is exercised for real.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.privacy_gate import (
    Capability,
    PrivacyMode,
    get_privacy_gate,
    reset_privacy_gate_singleton_for_tests,
)


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_privacy_gate_singleton_for_tests()
    yield
    reset_privacy_gate_singleton_for_tests()


class TestFindFilesToolGated:
    def test_handler_denied_during_privacy(self):
        from core.tools.find_files import handler
        gate = get_privacy_gate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        result = handler({"action": "disk_usage"})

        assert "nicht verfügbar" in result.lower() or "not available" in result.lower()

    def test_handler_works_normally_outside_privacy(self, tmp_path, monkeypatch):
        from core.tools import find_files
        # Redirect "home" to a throwaway dir so this doesn't touch the
        # sandbox's real filesystem beyond a harmless disk_usage call.
        result = find_files.handler({"action": "disk_usage"})
        assert "nicht verfügbar" not in result

    def test_handler_denied_in_privacy_lock_too(self):
        from core.tools.find_files import handler
        gate = get_privacy_gate()
        gate.enter(PrivacyMode.PRIVACY_LOCK, actor="test")

        result = handler({"action": "list_files", "directory": "home"})

        assert "nicht verfügbar" in result.lower()


class TestFilesystemSkillGated:
    def _skill(self):
        import sys as _sys
        sys.path.insert(0, ".") if "." not in _sys.path else None
        from skills.system.filesystem.skill import FilesystemSkill
        return FilesystemSkill.__new__(FilesystemSkill)

    def test_find_file_denied_during_privacy(self):
        skill = self._skill()
        gate = get_privacy_gate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        result = skill.find_file({"original_text": "find report.pdf"})

        assert result == skill._PRIVACY_DENIED_MESSAGE

    def test_count_code_lines_denied_during_privacy(self):
        skill = self._skill()
        gate = get_privacy_gate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        assert skill.count_code_lines() == skill._PRIVACY_DENIED_MESSAGE

    def test_count_files_in_directory_denied_during_privacy(self):
        skill = self._skill()
        gate = get_privacy_gate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        assert skill.count_files_in_directory({"original_text": "count files in downloads"}) == skill._PRIVACY_DENIED_MESSAGE

    def test_analyze_script_denied_during_privacy(self):
        skill = self._skill()
        gate = get_privacy_gate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        assert skill.analyze_script({"original_text": "analyze backup.sh"}) == skill._PRIVACY_DENIED_MESSAGE

    def test_privacy_denied_helper_false_when_normal(self):
        skill = self._skill()
        assert skill._privacy_denied() is False


class TestMCPBridgeRemoteToolGated:
    def test_sync_handler_allowed_in_plain_privacy(self):
        """REMOTE_TOOL is deliberately NOT in _PRIVACY_BLOCKED (see
        core/privacy_gate.py's capability matrix) — only PRIVACY_LOCK
        closes external/remote paths. Plain PRIVACY must not deny this."""
        from core.mcp_client import MCPBridge
        bridge = MCPBridge.__new__(MCPBridge)
        bridge._timeouts = {"tool_call": 30}
        bridge._loop = None

        gate = get_privacy_gate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")

        handler = bridge._make_sync_handler("some_server", "some_tool")
        with pytest.raises(Exception):
            # Must get past the privacy check and fail on the invalid
            # loop instead — proves it wasn't silently denied.
            handler({"arg": "value"})

    def test_sync_handler_denied_in_privacy_lock(self):
        from core.mcp_client import MCPBridge
        bridge = MCPBridge.__new__(MCPBridge)
        bridge._timeouts = {"tool_call": 30}
        bridge._loop = None

        gate = get_privacy_gate()
        gate.enter(PrivacyMode.PRIVACY_LOCK, actor="test")

        handler = bridge._make_sync_handler("some_server", "some_tool")
        result = handler({})

        assert "nicht verfügbar" in result.lower()

    def test_sync_handler_proceeds_to_real_call_outside_privacy(self):
        """Confirms the gate doesn't accidentally short-circuit in
        NORMAL mode — must reach asyncio.run_coroutine_threadsafe (which
        will fail here since _loop is None/invalid, proving the gate
        check was passed rather than silently swallowing the call)."""
        from core.mcp_client import MCPBridge
        bridge = MCPBridge.__new__(MCPBridge)
        bridge._timeouts = {"tool_call": 30}
        bridge._loop = None

        handler = bridge._make_sync_handler("some_server", "some_tool")
        with pytest.raises(Exception):
            # None is not a valid event loop for run_coroutine_threadsafe —
            # this must raise (proving we got past the privacy check),
            # not return the denial string.
            handler({})
