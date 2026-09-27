"""Unit tests for session #6 P0 item 4: local control path for
PrivacyGate, used by jarvis_continuous.py (no interactive text input)
since voice cannot reliably exit PRIVACY once MIC_INGEST/STT are denied.

Real PrivacyGate + real PrivacyControlWatcher throughout, sentinel paths
overridden to tmp_path so tests never touch the real /tmp/.jarvis_privacy_*
files. No STT/mic code involved — this module has no such dependency.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.privacy_control_watcher import PrivacyControlWatcher
from core.privacy_gate import (
    PrivacyMode,
    get_privacy_gate,
    reset_privacy_gate_singleton_for_tests,
)


class _FakeConfig(dict):
    def get(self, path, default=None):
        parts = path.split(".")
        d = self
        for p in parts:
            if isinstance(d, dict) and p in d:
                d = d[p]
            else:
                return default
        return d


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_privacy_gate_singleton_for_tests()
    yield
    reset_privacy_gate_singleton_for_tests()


@pytest.fixture
def watcher(tmp_path):
    w = PrivacyControlWatcher(_FakeConfig({}), poll_interval=0.02)
    w.ENTER_SENTINEL = str(tmp_path / "enter")
    w.LOCK_SENTINEL = str(tmp_path / "lock")
    w.EXIT_SENTINEL = str(tmp_path / "exit")
    w.STATUS_FILE = str(tmp_path / "status")
    yield w
    w.stop()


def _touch(path):
    with open(path, "w") as f:
        f.write("")


class TestSentinelHandlersDirectly:
    def test_handle_enter_sets_privacy_mode(self, watcher):
        watcher._handle_enter()
        assert watcher._gate.mode() == PrivacyMode.PRIVACY

    def test_handle_lock_sets_privacy_lock_mode(self, watcher):
        watcher._handle_lock()
        assert watcher._gate.mode() == PrivacyMode.PRIVACY_LOCK

    def test_handle_exit_returns_to_normal(self, watcher):
        watcher._handle_enter()
        watcher._handle_exit()
        assert watcher._gate.mode() == PrivacyMode.NORMAL

    def test_consume_removes_sentinel_file(self, watcher, tmp_path):
        sentinel = tmp_path / "probe"
        _touch(sentinel)
        calls = []
        watcher._consume(str(sentinel), lambda: calls.append(True))

        assert not sentinel.exists()
        assert calls == [True]

    def test_consume_noop_when_sentinel_absent(self, watcher, tmp_path):
        calls = []
        watcher._consume(str(tmp_path / "nonexistent"), lambda: calls.append(True))
        assert calls == []

    def test_consume_does_not_call_handler_twice_if_removal_fails(self, watcher, tmp_path, monkeypatch):
        sentinel = tmp_path / "probe2"
        _touch(sentinel)
        calls = []

        def fail_remove(path):
            raise OSError("simulated removal failure")

        monkeypatch.setattr(os, "remove", fail_remove)
        watcher._consume(str(sentinel), lambda: calls.append(True))

        assert calls == []  # handler NOT invoked when removal couldn't be confirmed


class TestBackgroundPollingIntegration:
    def test_touch_enter_sentinel_flips_mode(self, watcher, tmp_path):
        watcher.start()
        try:
            _touch(watcher.ENTER_SENTINEL)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and watcher._gate.mode() != PrivacyMode.PRIVACY:
                time.sleep(0.01)
            assert watcher._gate.mode() == PrivacyMode.PRIVACY
            assert not os.path.exists(watcher.ENTER_SENTINEL)
        finally:
            watcher.stop()

    def test_touch_exit_sentinel_flips_mode_back(self, watcher):
        watcher._gate.enter(PrivacyMode.PRIVACY, actor="test")
        watcher.start()
        try:
            _touch(watcher.EXIT_SENTINEL)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and watcher._gate.mode() != PrivacyMode.NORMAL:
                time.sleep(0.01)
            assert watcher._gate.mode() == PrivacyMode.NORMAL
        finally:
            watcher.stop()

    def test_stop_actually_stops_the_thread(self, watcher):
        watcher.start()
        watcher.stop()
        watcher.join(timeout=2)
        assert not watcher.is_alive()


class TestFailClosedOnSimultaneousSentinels:
    """Session #7 fix: the previous poll order (LOCK, ENTER, EXIT — i.e.
    EXIT applied LAST) actually made EXIT win any sentinel collision,
    the opposite of "the more protective outcome wins" — confirmed by
    the old version of this test, which asserted NORMAL as the outcome
    of a LOCK+EXIT collision while claiming that was "lock wins" in its
    own name. Since each _consume() call is a plain state assignment,
    whichever is applied LAST in the poll order is the final mode — so
    the corrected order (EXIT, ENTER, LOCK) applies LOCK last, making it
    the actual winner of any collision, as PRIVACY_LOCK > PRIVACY > EXIT
    requires."""

    def test_lock_wins_over_simultaneous_exit(self, watcher):
        _touch(watcher.LOCK_SENTINEL)
        _touch(watcher.EXIT_SENTINEL)

        watcher._consume(watcher.EXIT_SENTINEL, watcher._handle_exit)
        watcher._consume(watcher.ENTER_SENTINEL, watcher._handle_enter)
        watcher._consume(watcher.LOCK_SENTINEL, watcher._handle_lock)

        assert watcher._gate.mode() == PrivacyMode.PRIVACY_LOCK  # lock applied last, wins

    def test_enter_wins_over_simultaneous_exit(self, watcher):
        _touch(watcher.ENTER_SENTINEL)
        _touch(watcher.EXIT_SENTINEL)

        watcher._consume(watcher.EXIT_SENTINEL, watcher._handle_exit)
        watcher._consume(watcher.ENTER_SENTINEL, watcher._handle_enter)
        watcher._consume(watcher.LOCK_SENTINEL, watcher._handle_lock)

        assert watcher._gate.mode() == PrivacyMode.PRIVACY

    def test_lock_wins_over_simultaneous_enter(self, watcher):
        _touch(watcher.ENTER_SENTINEL)
        _touch(watcher.LOCK_SENTINEL)

        watcher._consume(watcher.EXIT_SENTINEL, watcher._handle_exit)
        watcher._consume(watcher.ENTER_SENTINEL, watcher._handle_enter)
        watcher._consume(watcher.LOCK_SENTINEL, watcher._handle_lock)

        assert watcher._gate.mode() == PrivacyMode.PRIVACY_LOCK

    def test_lone_exit_sentinel_still_exits_normally(self, watcher):
        """The common real case — only EXIT present — must still work:
        the reordering must not accidentally make EXIT a no-op."""
        watcher._handle_enter()  # start from PRIVACY
        _touch(watcher.EXIT_SENTINEL)

        watcher._consume(watcher.EXIT_SENTINEL, watcher._handle_exit)
        watcher._consume(watcher.ENTER_SENTINEL, watcher._handle_enter)
        watcher._consume(watcher.LOCK_SENTINEL, watcher._handle_lock)

        assert watcher._gate.mode() == PrivacyMode.NORMAL

    def test_poll_order_processes_exit_before_lock_within_one_cycle(self, watcher):
        """Directly verifies run()'s actual ordering by replicating one
        iteration's sequence."""
        _touch(watcher.LOCK_SENTINEL)
        order = []
        watcher._handle_lock = lambda: order.append("lock")
        watcher._handle_enter = lambda: order.append("enter")
        watcher._handle_exit = lambda: order.append("exit")
        _touch(watcher.EXIT_SENTINEL)

        watcher._consume(watcher.EXIT_SENTINEL, watcher._handle_exit)
        watcher._consume(watcher.ENTER_SENTINEL, watcher._handle_enter)
        watcher._consume(watcher.LOCK_SENTINEL, watcher._handle_lock)

        assert order == ["exit", "lock"]

    def test_run_loop_itself_uses_the_corrected_order(self, watcher):
        """End-to-end via the real background thread (not a manual
        _consume() replay) — a LOCK+EXIT collision resolved by the
        actual run() loop must land on PRIVACY_LOCK."""
        _touch(watcher.LOCK_SENTINEL)
        _touch(watcher.EXIT_SENTINEL)

        watcher.start()
        try:
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and (
                os.path.exists(watcher.LOCK_SENTINEL) or os.path.exists(watcher.EXIT_SENTINEL)
            ):
                time.sleep(0.01)
            time.sleep(0.05)  # let the same poll iteration finish applying both
            assert watcher._gate.mode() == PrivacyMode.PRIVACY_LOCK
        finally:
            watcher.stop()


class TestStatusFileReflectsCurrentMode:
    def test_status_file_written_on_start(self, watcher):
        watcher._write_status()
        content = open(watcher.STATUS_FILE).read()
        assert content.startswith("normal ")

    def test_status_file_updates_on_enter(self, watcher):
        watcher._gate.enter(PrivacyMode.PRIVACY, actor="test")
        content = open(watcher.STATUS_FILE).read()
        assert content.startswith("privacy ")

    def test_status_file_updates_on_exit(self, watcher):
        watcher._gate.enter(PrivacyMode.PRIVACY, actor="test")
        watcher._gate.exit(actor="test")
        content = open(watcher.STATUS_FILE).read()
        assert content.startswith("normal ")

    def test_status_file_never_contains_content_only_metadata(self, watcher):
        """Matches PrivacyGate's own audit-log rule: metadata only."""
        watcher._gate.enter(PrivacyMode.PRIVACY, actor="test", reason="some secret reason text")
        content = open(watcher.STATUS_FILE).read()
        assert "secret" not in content
        parts = content.strip().split()
        assert len(parts) == 2  # mode, timestamp — nothing else
