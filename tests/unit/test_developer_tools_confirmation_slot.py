"""Unit tests for session #7 agentic-audit finding #10: developer_tools'
pending-command confirmation slot was a single global variable — a
second confirmation-tier run_command call while one was already
pending silently overwrote it. A user confirming "yes" to what they
believed was the first command would then actually execute the second
one instead (and the LLM itself can issue a second run_command call
mid-conversation while a first confirmation is still outstanding, not
just a human typing quickly).
"""

import os
import sys
import time as _time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

import core.tools.developer_tools as devtools


@pytest.fixture(autouse=True)
def _clean_pending_slot():
    """The pending-command slot is module-level global state — reset it
    around every test so they don't leak into each other."""
    devtools._pending_command = None
    yield
    devtools._pending_command = None


@pytest.fixture(autouse=True)
def _stub_run_cmd(monkeypatch):
    """Never actually execute a shell command from these tests."""
    monkeypatch.setattr(devtools, "_run_cmd", lambda *a, **k: "stubbed output")


@pytest.fixture(autouse=True)
def _stub_get_safety(monkeypatch):
    """_get_safety() dynamically loads _safety.py from a hardcoded
    deployment path (/home/alex/jarvis-data/skills/...) that doesn't
    exist in this sandbox checkout — use the real module via its normal
    package import instead, sidestepping the deployment-path loader
    entirely (the classifier logic itself is exercised for real either
    way, just imported normally)."""
    from skills.system.developer_tools import _safety as real_safety
    monkeypatch.setattr(devtools, "_get_safety", lambda: real_safety)


class TestSecondConfirmationDoesNotOverwriteFirst:
    def test_second_pending_command_is_refused_not_overwritten(self):
        first = devtools._devtools_run_command({"command": "rm first_file.txt"})
        assert "Bestätigung erforderlich" in first
        assert devtools._pending_command[0] == "rm first_file.txt"

        second = devtools._devtools_run_command({"command": "rm second_file.txt"})

        assert "wartet bereits auf Bestätigung" in second
        assert "rm first_file.txt" in second
        # The pending slot must still hold the FIRST command, unchanged.
        assert devtools._pending_command[0] == "rm first_file.txt"

    def test_confirming_after_refused_second_runs_the_first_command(self):
        devtools._devtools_run_command({"command": "rm first_file.txt"})
        devtools._devtools_run_command({"command": "rm second_file.txt"})  # refused

        result = devtools._devtools_confirm_pending({})

        assert result == "stubbed output"
        # (implicitly: _run_cmd was called with the first command, since
        # that's the only one that could have been the pending slot —
        # verified more directly below)

    def test_confirming_after_refused_second_actually_runs_the_correct_command(self, monkeypatch):
        calls = []
        monkeypatch.setattr(devtools, "_run_cmd", lambda cmd, **k: calls.append(cmd) or "ok")

        devtools._devtools_run_command({"command": "rm first_file.txt"})
        devtools._devtools_run_command({"command": "rm second_file.txt"})  # refused
        devtools._devtools_confirm_pending({})

        assert calls == ["rm first_file.txt"]  # never the second, silently-overwritten one

    def test_new_command_accepted_after_first_is_confirmed(self):
        devtools._devtools_run_command({"command": "rm first_file.txt"})
        devtools._devtools_confirm_pending({})  # resolves the first

        second = devtools._devtools_run_command({"command": "rm second_file.txt"})

        assert "Bestätigung erforderlich" in second
        assert devtools._pending_command[0] == "rm second_file.txt"

    def test_new_command_accepted_after_first_expires(self):
        devtools._devtools_run_command({"command": "rm first_file.txt"})
        # Force the pending slot into the past, simulating expiry.
        devtools._pending_command = ("rm first_file.txt", _time.time() - 1)

        second = devtools._devtools_run_command({"command": "rm second_file.txt"})

        assert "Bestätigung erforderlich" in second
        assert devtools._pending_command[0] == "rm second_file.txt"

    def test_no_pending_command_accepts_normally(self):
        result = devtools._devtools_run_command({"command": "rm somefile.txt"})
        assert "Bestätigung erforderlich" in result
        assert "already awaiting" not in result
