"""Unit tests for the candidate/confirmed memory tier additions to
core/memory_manager.py: reinforcement (repeated evidence), the existing
subject-based dedup/supersede mechanism, and is_candidate() semantics.

Uses a real (temp-file) SQLite DB — MemoryManager's fact store is thin
enough over SQLite that mocking it would just re-implement the tests
against a fake; no embedding model or FAISS is needed for any of this
(embedding_model=None throughout, matching how the class already
degrades gracefully without one).
"""

import os
import sys
import tempfile
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
        },
    })
    manager = MemoryManager(cfg, conversation=None, embedding_model=None)
    yield manager


def _fact(content, subject="editor", category="preference",
          source="explicit", confidence=0.90, user_id="primary_user"):
    return {
        "user_id": user_id,
        "category": category,
        "subject": subject,
        "content": content,
        "source": source,
        "confidence": confidence,
        "source_messages": "[]",
    }


class TestExplicitFactIsConfirmed:
    def test_explicit_high_confidence_not_a_candidate(self, mm):
        fid = mm.store_fact(_fact("the user's favorite editor is VS Code"))
        fact = mm.get_fact_by_id(fid)
        assert mm.is_candidate(fact) is False


class TestInferredObservationIsCandidate:
    def test_single_inferred_observation_is_candidate(self, mm):
        fid = mm.store_fact(_fact(
            "the user often opens VS Code for development",
            subject="editor_usage", source="inferred", confidence=0.70,
        ))
        fact = mm.get_fact_by_id(fid)
        assert mm.is_candidate(fact) is True


class TestReinforcement:
    def test_repeated_observation_increases_confidence_and_evidence(self, mm):
        fact = _fact(
            "the user often opens VS Code for development",
            subject="editor_usage", source="inferred", confidence=0.70,
        )
        fid1 = mm.store_fact(dict(fact))
        first = mm.get_fact_by_id(fid1)
        assert first["evidence_count"] == 1

        fid2 = mm.store_fact(dict(fact))  # identical content again
        assert fid2 == fid1  # same fact reinforced, not duplicated

        reinforced = mm.get_fact_by_id(fid1)
        assert reinforced["evidence_count"] == 2
        assert reinforced["confidence"] > first["confidence"]

    def test_reinforcement_can_promote_candidate_to_confirmed(self, mm):
        fact = _fact(
            "the user often opens VS Code for development",
            subject="editor_usage", source="inferred", confidence=0.79,
        )
        fid = mm.store_fact(dict(fact))
        assert mm.is_candidate(mm.get_fact_by_id(fid)) is True

        # Repeat until confidence crosses CANDIDATE_CONFIDENCE_THRESHOLD.
        for _ in range(5):
            mm.store_fact(dict(fact))

        promoted = mm.get_fact_by_id(fid)
        assert promoted["confidence"] >= mm.CANDIDATE_CONFIDENCE_THRESHOLD
        assert mm.is_candidate(promoted) is False

    def test_confidence_caps_at_max(self, mm):
        fact = _fact(
            "the user often opens VS Code for development",
            subject="editor_usage", source="inferred", confidence=0.97,
        )
        fid = mm.store_fact(dict(fact))
        for _ in range(10):
            mm.store_fact(dict(fact))
        result = mm.get_fact_by_id(fid)
        assert result["confidence"] <= mm.MAX_FACT_CONFIDENCE

    def test_no_duplicate_rows_created(self, mm):
        fact = _fact(
            "the user often opens VS Code for development",
            subject="editor_usage", source="inferred", confidence=0.70,
        )
        for _ in range(4):
            mm.store_fact(dict(fact))
        all_facts = mm.get_facts(category="preference")
        matching = [f for f in all_facts if f["subject"] == "editor_usage"]
        assert len(matching) == 1


class TestContradictionSupersedes:
    def test_same_subject_different_content_supersedes_old(self, mm):
        old_id = mm.store_fact(_fact(
            "the user's favorite editor is VS Code", subject="editor",
        ))
        new_id = mm.store_fact(_fact(
            "the user's favorite editor is Cursor", subject="editor",
        ))

        assert old_id != new_id
        # Old fact no longer active (superseded).
        assert mm.get_fact_by_id(old_id) is None
        active = mm.get_facts(category="preference")
        contents = [f["content"] for f in active]
        assert "the user's favorite editor is Cursor" in contents
        assert "the user's favorite editor is VS Code" not in contents

    def test_history_preserved_via_superseded_by(self, mm):
        old_id = mm.store_fact(_fact(
            "the user's favorite editor is VS Code", subject="editor",
        ))
        new_id = mm.store_fact(_fact(
            "the user's favorite editor is Cursor", subject="editor",
        ))
        with mm._db_lock:
            conn = mm._get_conn()
            row = conn.execute(
                "SELECT superseded_by, deleted FROM facts WHERE fact_id = ?",
                (old_id,),
            ).fetchone()
            conn.close()
        assert row["superseded_by"] == new_id
        assert row["deleted"] == 0  # history kept, not hard-deleted


class TestSubjectNormalization:
    def test_subject_casing_does_not_defeat_exact_match(self, mm):
        mm.store_fact(_fact(
            "the user's favorite editor is VS Code", subject="Editor",
        ))
        # Different casing/whitespace on the subject for the same
        # attribute must still hit the exact-match dedup path, not just
        # the weaker substring-fuzzy fallback.
        new_id = mm.store_fact(_fact(
            "the user's favorite editor is Cursor", subject="  editor ",
        ))
        active = mm.get_facts(category="preference")
        assert len(active) == 1
        assert active[0]["fact_id"] == new_id


class TestUnrelatedFactsCoexist:
    def test_different_subjects_both_stay_active(self, mm):
        mm.store_fact(_fact(
            "the user's favorite editor is VS Code", subject="editor",
        ))
        mm.store_fact(_fact(
            "the user's favorite shipping carrier is DHL", subject="carrier",
        ))
        active = mm.get_facts(category="preference")
        assert len(active) == 2
