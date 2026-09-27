"""Unit tests for session #8 agentic-audit finding #2: run_command and
confirm_pending (core/tools/developer_tools.py) used to cwd into a
hardcoded '/home/user/jarvis' — a stale/wrong path on the real Sleepy
deployment (config.yaml's own paths point elsewhere, e.g.
skill_manager.skills_path='/home/alex/jarvis/skills'). The fix derives
the real working directory from where the module itself actually runs
from (_JARVIS_ROOT = two directories up from this file), rather than
hardcoding a second guess.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

import core.tools.developer_tools as devtools


@pytest.fixture(autouse=True)
def _clean_pending_slot():
    devtools._pending_command = None
    yield
    devtools._pending_command = None


@pytest.fixture(autouse=True)
def _stub_get_safety(monkeypatch):
    from skills.system.developer_tools import _safety as real_safety
    monkeypatch.setattr(devtools, "_get_safety", lambda: real_safety)


class TestJarvisRootIsDerivedNotHardcoded:
    def test_jarvis_root_is_not_the_old_stale_hardcode(self):
        assert devtools._JARVIS_ROOT != "/home/user/jarvis"

    def test_jarvis_root_is_the_real_repo_root(self):
        # core/tools/developer_tools.py -> parent.parent.parent
        expected = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(devtools.__file__)))
        )
        assert devtools._JARVIS_ROOT == expected
        # Sanity: this directory actually exists and looks like the repo.
        assert os.path.isdir(devtools._JARVIS_ROOT)
        assert os.path.isdir(os.path.join(devtools._JARVIS_ROOT, "core"))


class TestRunCommandUsesRealCwd:
    def test_run_command_passes_jarvis_root_as_cwd(self, monkeypatch):
        seen_cwd = []

        def fake_run_cmd(cmd, cwd=None, timeout=15):
            seen_cwd.append(cwd)
            return "ok"

        monkeypatch.setattr(devtools, "_run_cmd", fake_run_cmd)

        # A Tier-1 read-only command executes immediately (no confirmation).
        devtools._devtools_run_command({"command": "git status"})

        assert seen_cwd == [devtools._JARVIS_ROOT]
        assert seen_cwd[0] != "/home/user/jarvis"

    def test_confirm_pending_passes_jarvis_root_as_cwd(self, monkeypatch):
        seen_cwd = []

        def fake_run_cmd(cmd, cwd=None, timeout=15):
            seen_cwd.append(cwd)
            return "ok"

        monkeypatch.setattr(devtools, "_run_cmd", fake_run_cmd)

        devtools._devtools_run_command({"command": "rm somefile.txt"})  # confirmation tier
        devtools._devtools_confirm_pending({})

        assert seen_cwd == [devtools._JARVIS_ROOT]
        assert seen_cwd[0] != "/home/user/jarvis"
