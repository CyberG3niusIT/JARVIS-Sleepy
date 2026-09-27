"""Unit tests for core/privacy_gate.py — the central PrivacyGate.

Covers the acceptance criteria from the privacy workstream:
PRIV-001 (audio/STT), PRIV-002 (screen), PRIV-003 (memory), PRIV-004
(cloud), PRIV-005 (exit / no catch-up ingestion), plus concurrency/race
behavior around enter()/exit() and epoch-gated background work.
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.privacy_gate import (
    Capability,
    PrivacyGate,
    PrivacyMode,
    PrivacyViolation,
    get_privacy_gate,
    reset_privacy_gate_singleton_for_tests,
)


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_privacy_gate_singleton_for_tests()
    yield
    reset_privacy_gate_singleton_for_tests()


class TestModeDefaultsAndTransitions:
    def test_default_mode_is_normal(self):
        gate = PrivacyGate()
        assert gate.mode() == PrivacyMode.NORMAL

    def test_enter_privacy_changes_mode(self):
        gate = PrivacyGate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        assert gate.mode() == PrivacyMode.PRIVACY

    def test_enter_privacy_lock_changes_mode(self):
        gate = PrivacyGate()
        gate.enter(PrivacyMode.PRIVACY_LOCK, actor="test")
        assert gate.mode() == PrivacyMode.PRIVACY_LOCK

    def test_enter_normal_rejected(self):
        gate = PrivacyGate()
        with pytest.raises(ValueError):
            gate.enter(PrivacyMode.NORMAL, actor="test")

    def test_exit_returns_to_normal(self):
        gate = PrivacyGate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        gate.exit(actor="test")
        assert gate.mode() == PrivacyMode.NORMAL

    def test_exit_when_already_normal_is_idempotent_noop(self):
        gate = PrivacyGate()
        gate.exit(actor="test")  # must not raise
        assert gate.mode() == PrivacyMode.NORMAL

    def test_singleton_returns_same_instance(self):
        a = get_privacy_gate()
        b = get_privacy_gate()
        assert a is b


class TestCapabilityMatrix:
    def test_normal_allows_everything(self):
        gate = PrivacyGate()
        for cap in Capability:
            assert gate.allow(cap) is True

    @pytest.mark.parametrize("cap", [
        Capability.MIC_INGEST,
        Capability.STT,
        Capability.SCREEN_CAPTURE,
        Capability.WEBCAM_CAPTURE,
        Capability.CLIPBOARD_READ,
        Capability.FILESYSTEM_OBSERVATION,
        Capability.MEMORY_EXTRACT,
        Capability.MEMORY_WRITE,
        Capability.EMBEDDING_GENERATE,
        Capability.SESSION_SUMMARY,
        Capability.AGENT_CONTEXT_INGEST,
        Capability.CLOUD_LLM,
        Capability.CONTENT_LOGGING,
        Capability.PROACTIVE_OBSERVATION,
    ])
    def test_privacy_blocks_data_paths(self, cap):
        gate = PrivacyGate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        assert gate.allow(cap) is False

    def test_privacy_lock_blocks_everything_privacy_blocks(self):
        gate = PrivacyGate()
        gate.enter(PrivacyMode.PRIVACY_LOCK, actor="test")
        for cap in Capability:
            if cap == Capability.REMOTE_TOOL:
                continue
            assert gate.allow(cap) is False

    def test_privacy_lock_additionally_blocks_remote_tool(self):
        gate = PrivacyGate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        assert gate.allow(Capability.REMOTE_TOOL) is True  # PRIVACY alone does not lock this
        gate.enter(PrivacyMode.PRIVACY_LOCK, actor="test")
        assert gate.allow(Capability.REMOTE_TOOL) is False

    def test_assert_allowed_raises_when_denied(self):
        gate = PrivacyGate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        with pytest.raises(PrivacyViolation):
            gate.assert_allowed(Capability.MIC_INGEST)

    def test_assert_allowed_silent_when_allowed(self):
        gate = PrivacyGate()
        gate.assert_allowed(Capability.MIC_INGEST)  # must not raise

    def test_exit_restores_all_capabilities(self):
        gate = PrivacyGate()
        gate.enter(PrivacyMode.PRIVACY_LOCK, actor="test")
        gate.exit(actor="test")
        for cap in Capability:
            assert gate.allow(cap) is True


class TestFlushCallbacksAndRaceSafety:
    def test_flush_callback_runs_on_enter(self):
        gate = PrivacyGate()
        calls = []
        gate.register_flush_callback(lambda: calls.append("flush"))
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        assert calls == ["flush"]

    def test_flush_callback_runs_on_exit_too(self):
        gate = PrivacyGate()
        calls = []
        gate.register_flush_callback(lambda: calls.append("flush"))
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        gate.exit(actor="test")
        assert calls == ["flush", "flush"]

    def test_flush_callback_exception_does_not_break_transition(self):
        gate = PrivacyGate()

        def boom():
            raise RuntimeError("simulated failure in a buffer-clear hook")

        gate.register_flush_callback(boom)
        gate.enter(PrivacyMode.PRIVACY, actor="test")  # must not raise
        assert gate.mode() == PrivacyMode.PRIVACY

    def test_enter_callback_receives_mode(self):
        gate = PrivacyGate()
        seen = []
        gate.register_enter_callback(lambda m: seen.append(m))
        gate.enter(PrivacyMode.PRIVACY_LOCK, actor="test")
        assert seen == [PrivacyMode.PRIVACY_LOCK]

    def test_exit_callback_fires(self):
        gate = PrivacyGate()
        seen = []
        gate.register_exit_callback(lambda: seen.append(True))
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        gate.exit(actor="test")
        assert seen == [True]

    def test_exit_callback_not_fired_on_noop_exit(self):
        gate = PrivacyGate()
        seen = []
        gate.register_exit_callback(lambda: seen.append(True))
        gate.exit(actor="test")  # already NORMAL
        assert seen == []


class TestEpochGuardsAgainstCatchUpIngestion:
    """This is the core PRIV-005 mechanism: background work captures the
    epoch before starting, and must refuse to write once the epoch has
    moved on — whether that's because privacy was entered *or* exited
    while the work was in flight.
    """

    def test_epoch_changes_on_enter(self):
        gate = PrivacyGate()
        e0 = gate.epoch()
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        assert gate.epoch() != e0

    def test_epoch_changes_on_exit(self):
        gate = PrivacyGate()
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        e1 = gate.epoch()
        gate.exit(actor="test")
        assert gate.epoch() != e1

    def test_is_current_epoch_true_when_unchanged(self):
        gate = PrivacyGate()
        e0 = gate.epoch()
        assert gate.is_current_epoch(e0) is True

    def test_work_started_before_privacy_cannot_land_after_exit(self):
        """Simulates: background extraction captures epoch, privacy is
        entered then exited while it's "running", and the deferred write
        must be rejected even though mode() is NORMAL again by the time
        it checks — a plain mode() re-check would wrongly allow this.
        """
        gate = PrivacyGate()
        captured_epoch = gate.epoch()  # background thread starts here

        gate.enter(PrivacyMode.PRIVACY, actor="test")
        gate.exit(actor="test")  # mode() is NORMAL again

        assert gate.mode() == PrivacyMode.NORMAL
        assert gate.is_current_epoch(captured_epoch) is False  # write must be rejected

    def test_work_started_during_normal_and_finishing_during_normal_is_current(self):
        gate = PrivacyGate()
        captured_epoch = gate.epoch()
        assert gate.is_current_epoch(captured_epoch) is True


class TestConcurrency:
    def test_concurrent_enter_exit_does_not_corrupt_state(self):
        gate = PrivacyGate()
        errors = []

        def toggle():
            try:
                for _ in range(200):
                    gate.enter(PrivacyMode.PRIVACY, actor="thread")
                    gate.exit(actor="thread")
            except Exception as e:  # pragma: no cover - failure diagnostic
                errors.append(e)

        threads = [threading.Thread(target=toggle) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        assert gate.mode() == PrivacyMode.NORMAL

    def test_concurrent_allow_checks_never_see_torn_state(self):
        """While one thread flips modes rapidly, allow() must always
        return a boolean consistent with *some* valid mode — never raise,
        never hang."""
        gate = PrivacyGate()
        stop = threading.Event()
        errors = []

        def flipper():
            while not stop.is_set():
                gate.enter(PrivacyMode.PRIVACY, actor="thread")
                gate.enter(PrivacyMode.PRIVACY_LOCK, actor="thread")
                gate.exit(actor="thread")

        def checker():
            try:
                for _ in range(2000):
                    gate.allow(Capability.MIC_INGEST)
                    gate.mode()
                    gate.epoch()
            except Exception as e:  # pragma: no cover
                errors.append(e)

        t_flip = threading.Thread(target=flipper, daemon=True)
        t_check = threading.Thread(target=checker)
        t_flip.start()
        t_check.start()
        t_check.join(timeout=10)
        stop.set()
        t_flip.join(timeout=2)

        assert not errors
