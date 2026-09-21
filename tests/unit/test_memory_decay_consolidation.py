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


class TestMergeDuplicateExcludedCandidates:
    """Session #7 finding: run_consolidation() claimed to be
    "decay only" while being named as if it did full consolidation.
    Rather than just renaming, this adds a real, bounded, deterministic
    MERGE step: repeated identical conflicting inferences (see the
    excluded_from_matching fix) each create their own row by design —
    this collapses exact duplicates into one, summing evidence_count as
    an observation counter, WITHOUT ever letting that sum affect
    confidence or re-enable matching (which would reopen the escalation
    bug that fix closed).

    Uses its own fixture with a high consolidation_interval_candidates
    so the "N new candidates" auto-trigger (tested separately above)
    doesn't fire mid-test and merge things before the explicit
    run_consolidation() call these tests are checking."""

    @pytest.fixture
    def mm(self, tmp_path):
        cfg = _FakeConfig({
            "conversational_memory": {
                "db_path": str(tmp_path / "memory_merge.db"),
                "faiss_index_path": str(tmp_path / "faiss_merge"),
                "autonomy_budget": {
                    "decay_days": 14,
                    "max_new_candidates": 500,
                    "max_consolidation_runs": 50,
                    "consolidation_interval_candidates": 1000,
                },
            },
        })
        return MemoryManager(cfg, conversation=None, embedding_model=None)

    def test_exact_duplicate_conflicting_candidates_get_merged(self, mm):
        fid_explicit = mm.store_fact(_fact(
            "Alex hasst Pizza", subject="pizza", value="pizza", source="explicit",
        ))
        fids = []
        for _ in range(5):
            fid = mm.store_fact(_fact(
                "Alex liebt Pizza", subject="pizza", value="pizza",
                source="inferred", confidence=0.70,
            ))
            fids.append(fid)
        assert len(set(fids)) == 5  # each conflict created its own row, as designed

        result = mm.run_consolidation()

        assert result["merged_count"] == 4  # 5 rows -> 1 canonical + 4 merged-away
        canonical = _raw_fact(mm, fids[0])  # oldest survives
        assert canonical["evidence_count"] == 5
        assert canonical["superseded_by"] is None
        for fid in fids[1:]:
            assert _raw_fact(mm, fid)["superseded_by"] == fids[0]

    def test_merge_never_changes_confidence(self, mm):
        mm.store_fact(_fact(
            "Alex hasst Pizza", subject="pizza", value="pizza", source="explicit",
        ))
        fids = [mm.store_fact(_fact(
            "Alex liebt Pizza", subject="pizza", value="pizza",
            source="inferred", confidence=0.70,
        )) for _ in range(6)]

        mm.run_consolidation()

        canonical = _raw_fact(mm, fids[0])
        assert canonical["confidence"] == pytest.approx(0.70)  # unchanged despite 6x evidence
        assert mm.is_candidate(canonical) is True  # still a candidate, never promoted

    def test_merged_row_stays_excluded_from_matching_and_get_facts(self, mm):
        mm.store_fact(_fact(
            "Alex hasst Pizza", subject="pizza", value="pizza", source="explicit",
        ))
        fids = [mm.store_fact(_fact(
            "Alex liebt Pizza", subject="pizza", value="pizza",
            source="inferred", confidence=0.70,
        )) for _ in range(3)]
        mm.run_consolidation()

        # A 4th identical conflicting observation must still create its
        # own new row, not reinforce the merged canonical.
        fid_new = mm.store_fact(_fact(
            "Alex liebt Pizza", subject="pizza", value="pizza",
            source="inferred", confidence=0.70,
        ))
        assert fid_new not in fids
        assert _raw_fact(mm, fids[0])["evidence_count"] == 3  # unchanged by the 4th observation

        facts = mm.get_facts("primary_user", category="preference")
        merged_away_ids = {fids[1], fids[2]}
        assert all(f["fact_id"] not in merged_away_ids for f in facts)

    def test_non_duplicate_candidates_not_merged(self, mm):
        mm.store_fact(_fact(
            "Alex hasst Pizza", subject="pizza", value="pizza", source="explicit",
        ))
        fid1 = mm.store_fact(_fact(
            "Alex liebt Pizza", subject="pizza", value="pizza",
            source="inferred", confidence=0.70,
        ))
        fid2 = mm.store_fact(_fact(
            "Alex mag Pizza total gern", subject="pizza", value="pizza",  # different content
            source="inferred", confidence=0.70,
        ))

        result = mm.run_consolidation()

        assert result["merged_count"] == 0
        assert _raw_fact(mm, fid1)["superseded_by"] is None
        assert _raw_fact(mm, fid2)["superseded_by"] is None

    def test_explicit_facts_never_touched_by_merge(self, mm):
        """MERGE only ever operates on excluded_from_matching=1 rows —
        explicit facts (excluded_from_matching=0) must never be
        candidates for merging even if somehow duplicated."""
        fid1 = mm.store_fact(_fact(
            "Alex hasst Pizza", subject="pizza", value="pizza", source="explicit",
        ))
        fid2 = mm.store_fact(_fact(  # different value -> real change -> supersede
            "Alex liebt Pizza", subject="pizza", value="pizza gerne", source="explicit",
        ))
        assert fid2 != fid1

        mm.run_consolidation()

        # Superseded via the normal explicit-correction path, not merge.
        assert _raw_fact(mm, fid1)["superseded_by"] == fid2


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
