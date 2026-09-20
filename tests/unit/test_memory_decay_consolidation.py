"""Unit tests for session #6 memory workstream: decay, bounded
consolidation, and the autonomy budget. Real temp-file SQLite (same
pattern as test_memory_manager_tiers.py).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.memory_manager import MemoryManager


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


@pytest.fixture
def mm(tmp_path):
    cfg = _FakeConfig({
        "conversational_memory": {
            "db_path": str(tmp_path / "memory.db"),
            "faiss_index_path": str(tmp_path / "faiss"),
            "autonomy_budget": {
                "decay_days": 14,
                "max_new_candidates": 5,
                "max_consolidation_runs": 3,
                "consolidation_interval_candidates": 4,
            },
        },
    })
    return MemoryManager(cfg, conversation=None, embedding_model=None)


def _fact(content, subject, category="preference", source="explicit",
          confidence=0.90, user_id="primary_user", value=None):
    return {
        "user_id": user_id, "category": category, "subject": subject,
        "content": content, "value": value, "source": source,
        "confidence": confidence, "source_messages": "[]",
    }


def _raw_fact(mm, fact_id):
    conn = mm._get_conn()
    try:
        row = conn.execute("SELECT * FROM facts WHERE fact_id = ?", (fact_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _set_created_at(mm, fact_id, ts):
    conn = mm._get_conn()
    try:
        conn.execute("UPDATE facts SET created_at = ? WHERE fact_id = ?", (ts, fact_id))
        conn.commit()
    finally:
        conn.close()


class TestDecayArchivesOnlyStaleUnreinforcedCandidates:
    def test_old_low_evidence_candidate_gets_archived(self, mm):
        fid = mm.store_fact(_fact(
            "Alex mag Kaffee", subject="kaffee", source="inferred", confidence=0.70,
        ))
        _set_created_at(mm, fid, time.time() - 30 * 86400)  # 30 days old

        result = mm.run_decay_pass()

        assert fid in result["archived_fact_ids"]
        assert _raw_fact(mm, fid)["archived"] == 1

    def test_recent_low_evidence_candidate_not_archived(self, mm):
        fid = mm.store_fact(_fact(
            "Alex mag Tee", subject="tee", source="inferred", confidence=0.70,
        ))
        # Created "now" — well within decay_days=14.

        result = mm.run_decay_pass()

        assert fid not in result["archived_fact_ids"]
        assert _raw_fact(mm, fid)["archived"] == 0

    def test_explicit_fact_never_decays_regardless_of_age(self, mm):
        fid = mm.store_fact(_fact(
            "Alex wohnt in Berlin", subject="wohnort", source="explicit", confidence=0.90,
        ))
        _set_created_at(mm, fid, time.time() - 365 * 86400)  # 1 year old

        result = mm.run_decay_pass()

        assert fid not in result["archived_fact_ids"]
        assert _raw_fact(mm, fid)["archived"] == 0

    def test_reinforced_candidate_never_decays(self, mm):
        fid1 = mm.store_fact(_fact(
            "Alex mag Pizza", subject="pizza", value="pizza", source="inferred", confidence=0.70,
        ))
        fid2 = mm.store_fact(_fact(  # same subject/value -> reinforces fid1
            "Alex mag Pizza sehr", subject="pizza", value="pizza", source="inferred", confidence=0.70,
        ))
        assert fid1 == fid2  # confirms reinforcement happened, not a new row
        _set_created_at(mm, fid1, time.time() - 30 * 86400)

        result = mm.run_decay_pass()

        assert fid1 not in result["archived_fact_ids"]
        row = _raw_fact(mm, fid1)
        assert row["evidence_count"] == 2  # was reinforced
        assert row["archived"] == 0

    def test_archived_fact_excluded_from_get_facts(self, mm):
        fid = mm.store_fact(_fact(
            "Alex mag Kaffee", subject="kaffee", source="inferred", confidence=0.70,
        ))
        _set_created_at(mm, fid, time.time() - 30 * 86400)
        mm.run_decay_pass()

        facts = mm.get_facts("primary_user", category="preference")
        assert all(f["fact_id"] != fid for f in facts)

    def test_archived_fact_excluded_from_matching(self, mm):
        """Once archived, a later new observation about the same subject
        must not reinforce the archived row — it should create a fresh
        candidate instead."""
        fid_old = mm.store_fact(_fact(
            "Alex mag Kaffee", subject="kaffee", value="kaffee",
            source="inferred", confidence=0.70,
        ))
        _set_created_at(mm, fid_old, time.time() - 30 * 86400)
        mm.run_decay_pass()
        assert _raw_fact(mm, fid_old)["archived"] == 1

        fid_new = mm.store_fact(_fact(
            "Alex mag Kaffee", subject="kaffee", value="kaffee",
            source="inferred", confidence=0.70,
        ))

        assert fid_new != fid_old
        assert _raw_fact(mm, fid_old)["evidence_count"] == 1  # untouched


class TestBoundedConsolidation:
    def test_run_consolidation_calls_decay(self, mm):
        fid = mm.store_fact(_fact(
            "Alex mag Kaffee", subject="kaffee", source="inferred", confidence=0.70,
        ))
        _set_created_at(mm, fid, time.time() - 30 * 86400)

        result = mm.run_consolidation()

        assert result["skipped"] is False
        assert fid in result["archived_fact_ids"]

    def test_consolidation_run_budget_enforced(self, mm):
        # fixture caps max_consolidation_runs at 3
        for _ in range(3):
            result = mm.run_consolidation()
            assert result["skipped"] is False

        result = mm.run_consolidation()
        assert result["skipped"] is True
        assert result["reason"] == "budget_exceeded"

    def test_consolidation_triggered_every_n_candidates(self, mm):
        """fixture sets consolidation_interval_candidates=4 — the 4th
        new (non-explicit) candidate should trigger a consolidation run
        automatically."""
        assert mm._consolidation_runs == 0
        for i in range(4):
            mm.store_fact(_fact(
                f"Alex mag Ding{i}", subject=f"ding{i}", source="inferred", confidence=0.70,
            ))
        assert mm._consolidation_runs == 1


class TestAutonomyBudgetCapsNewCandidates:
    def test_new_candidates_denied_past_budget(self, mm):
        # fixture caps max_new_candidates at 5
        created = []
        for i in range(7):
            fid = mm.store_fact(_fact(
                f"Alex mag Sache{i}", subject=f"sache{i}", source="inferred", confidence=0.70,
            ))
            created.append(fid)

        successful = [c for c in created if c is not None]
        denied = [c for c in created if c is None]
        assert len(successful) == 5
        assert len(denied) == 2

    def test_explicit_facts_never_budget_limited(self, mm):
        # Exhaust the budget with inferred candidates first.
        for i in range(5):
            mm.store_fact(_fact(
                f"Alex mag Sache{i}", subject=f"sache{i}", source="inferred", confidence=0.70,
            ))
        assert mm.store_fact(_fact(
            "Alex mag noch was", subject="sache5", source="inferred", confidence=0.70,
        )) is None  # budget exhausted for inferred

        fid = mm.store_fact(_fact(
            "Alex wohnt in Hamburg", subject="wohnort", source="explicit", confidence=0.90,
        ))
        assert fid is not None  # explicit is never budget-limited

    def test_reinforcement_does_not_count_against_budget(self, mm):
        """Only genuinely NEW rows count — repeated reinforcement of the
        same candidate must not burn through the budget."""
        for _ in range(10):
            fid = mm.store_fact(_fact(
                "Alex mag Pizza", subject="pizza", value="pizza",
                source="inferred", confidence=0.70,
            ))
        assert fid is not None  # all 10 calls reinforced the same row
        assert mm._new_candidates_created == 1
