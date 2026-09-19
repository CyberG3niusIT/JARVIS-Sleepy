"""Integration tests: PrivacyGate wired into MemoryManager (PRIV-003).

Real temp-file SQLite (same pattern as test_memory_manager_tiers.py) —
no mocking of the DB layer. Verifies that while privacy is active, no
candidate, short-term, or long-term fact/embedding write happens, and
that a background extraction "in flight" across a privacy transition
cannot land its write afterwards (the epoch mechanism).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.memory_manager import MemoryManager
from core.privacy_gate import (
    Capability,
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
def cfg(tmp_path):
    return _FakeConfig({
        "conversational_memory": {
            "db_path": str(tmp_path / "memory.db"),
            "faiss_index_path": str(tmp_path / "faiss"),
        },
    })


@pytest.fixture
def mm(cfg):
    return MemoryManager(cfg, conversation=None, embedding_model=None)


def _fact(content, subject="editor", category="preference",
          source="explicit", confidence=0.90, user_id="primary_user",
          value=None):
    return {
        "user_id": user_id, "category": category, "subject": subject,
        "content": content, "value": value, "source": source,
        "confidence": confidence, "source_messages": "[]",
    }


class TestStoreFactDeniedDuringPrivacy:
    def test_store_fact_writes_normally(self, mm):
        fid = mm.store_fact(_fact("the user's favorite editor is VS Code"))
        assert fid is not None
        assert mm.get_fact_by_id(fid) is not None

    def test_store_fact_denied_in_privacy(self, mm, cfg):
        gate = get_privacy_gate(cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        fid = mm.store_fact(_fact("the user's favorite editor is VS Code"))
        assert fid is None

    def test_store_fact_denied_in_privacy_lock(self, mm, cfg):
        gate = get_privacy_gate(cfg)
        gate.enter(PrivacyMode.PRIVACY_LOCK, actor="test")
        fid = mm.store_fact(_fact("the user's favorite editor is VS Code"))
        assert fid is None

    def test_no_row_persisted_when_denied(self, mm, cfg):
        gate = get_privacy_gate(cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        mm.store_fact(_fact("the user's favorite editor is VS Code"))
        gate.exit(actor="test")
        # Nothing should have been persisted — confirm via a fresh recall.
        assert mm.get_facts("primary_user") == []

    def test_store_fact_works_again_after_exit(self, mm, cfg):
        gate = get_privacy_gate(cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        gate.exit(actor="test")
        fid = mm.store_fact(_fact("the user's favorite editor is VS Code"))
        assert fid is not None


class TestOnMessageDeniedDuringPrivacy:
    def test_on_message_skips_indexing_and_extraction_in_privacy(self, mm, cfg):
        gate = get_privacy_gate(cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        # Should not raise and should be a pure no-op.
        mm.on_message({"role": "user", "content": "ich wohne in Berlin und mag Tee", "user_id": "primary_user"})
        assert mm.last_extracted == [] or not hasattr(mm, "last_extracted")

    def test_index_message_denied_in_privacy(self, mm, cfg):
        gate = get_privacy_gate(cfg)
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        # Must not raise even without an embedding model.
        mm.index_message({"role": "user", "content": "irrelevant probe content here"})


class TestEpochRaceOnBackgroundExtraction:
    """Simulates the exact race the workstream calls out: extraction
    triggered while NORMAL, privacy entered mid-flight, and the
    background thread's store_fact call must be rejected — via the
    epoch check, not just the live mode() check (which would already
    read NORMAL again after an enter+exit pair completes first)."""

    def test_captured_epoch_rejects_write_after_transition(self, mm, cfg):
        gate = get_privacy_gate(cfg)
        captured_epoch = gate.epoch()

        gate.enter(PrivacyMode.PRIVACY, actor="test")
        gate.exit(actor="test")  # mode() is NORMAL again, but epoch moved twice

        assert gate.mode() == PrivacyMode.NORMAL
        assert gate.is_current_epoch(captured_epoch) is False

        # _run_batch_extraction/_run_per_turn_extraction both bail out
        # immediately when the captured epoch is stale — exercise that
        # directly rather than mocking the LLM call.
        mm._run_batch_extraction(captured_epoch=captured_epoch)
        assert mm.get_facts("primary_user") == []

    def test_per_turn_extraction_bails_out_on_stale_epoch(self, mm, cfg):
        gate = get_privacy_gate(cfg)
        captured_epoch = gate.epoch()
        gate.enter(PrivacyMode.PRIVACY, actor="test")
        gate.exit(actor="test")

        mm._run_per_turn_extraction("ich mag Kaffee", "Notiert.", "primary_user", captured_epoch=captured_epoch)
        assert mm._per_turn_in_progress is False
        assert mm.get_facts("primary_user") == []
