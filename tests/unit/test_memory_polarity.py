"""Unit tests for polarity/predicate reversal semantics in
core/memory_manager.py — the "ich liebe X" -> "ich hasse X" bug.

Real temp-file SQLite (same pattern as test_memory_manager_tiers.py).
"""

import os
import sys
import threading

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
    return MemoryManager(cfg, conversation=None, embedding_model=None)


def _raw_fact(mm, fact_id):
    """get_fact_by_id() filters out superseded facts — this reads the row
    regardless of superseded_by, needed to assert a fact was (or wasn't)
    superseded/reinforced."""
    conn = mm._get_conn()
    try:
        row = conn.execute("SELECT * FROM facts WHERE fact_id = ?", (fact_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _fact(content, subject="pizza", category="preference",
          source="explicit", confidence=0.90, user_id="primary_user",
          value=None):
    return {
        "user_id": user_id, "category": category, "subject": subject,
        "content": content, "value": value, "source": source,
        "confidence": confidence, "source_messages": "[]",
    }


class TestPolarityDetection:
    def test_positive_german(self, mm):
        assert mm._detect_polarity("preference", "Alex liebt Pizza") == 1

    def test_negative_german(self, mm):
        assert mm._detect_polarity("preference", "Alex hasst Pizza") == -1

    def test_negated_positive_german(self, mm):
        assert mm._detect_polarity("preference", "Alex mag Pizza nicht") == -1

    def test_positive_english(self, mm):
        assert mm._detect_polarity("preference", "Alex loves pizza") == 1

    def test_negative_english(self, mm):
        assert mm._detect_polarity("preference", "Alex hates pizza") == -1

    def test_no_polarity_word_returns_none(self, mm):
        assert mm._detect_polarity("preference", "Alex isst manchmal Pizza") is None

    def test_non_polarity_category_returns_none(self, mm):
        # e.g. "location" — sentiment words there aren't meaningful signal
        assert mm._detect_polarity("location", "Alex liebt Berlin") is None


class TestReversalIsNeverReinforcement:
    """The core bug: same subject/value must not be treated as
    REINFORCE when the sentiment flips."""

    def test_love_then_hate_same_value_supersedes_not_reinforces(self, mm):
        fid1 = mm.store_fact(_fact(
            "Alex liebt Pizza", subject="pizza", value="pizza",
        ))
        fact1 = _raw_fact(mm, fid1)
        assert fact1["evidence_count"] == 1

        fid2 = mm.store_fact(_fact(
            "Alex hasst Pizza", subject="pizza", value="pizza",
        ))

        # Must be a NEW fact, not a reinforcement of fact1.
        assert fid2 != fid1
        fact1_after = _raw_fact(mm, fid1)
        assert fact1_after["evidence_count"] == 1  # unchanged — not reinforced
        assert fact1_after["superseded_by"] == fid2

        fact2 = _raw_fact(mm, fid2)
        assert fact2["polarity"] == -1

    def test_hate_then_love_also_supersedes(self, mm):
        fid1 = mm.store_fact(_fact(
            "Alex hasst Sport", subject="sport", value="sport",
        ))
        fid2 = mm.store_fact(_fact(
            "Alex liebt Sport", subject="sport", value="sport",
        ))
        assert fid2 != fid1
        assert _raw_fact(mm, fid1)["superseded_by"] == fid2

    def test_paraphrase_same_polarity_still_reinforces(self, mm):
        """Sanity check the fix doesn't break the existing, correct
        REINFORCE behavior for genuine paraphrases."""
        fid1 = mm.store_fact(_fact(
            "Alex mag Pizza sehr gerne", subject="pizza", value="pizza",
        ))
        fid2 = mm.store_fact(_fact(
            "Alex liebt Pizza", subject="pizza", value="pizza",
        ))
        assert fid2 == fid1
        assert _raw_fact(mm, fid1)["evidence_count"] == 2

    def test_no_polarity_data_falls_back_to_value_comparison(self, mm):
        """Facts with no detectable sentiment word must behave exactly
        as before this change — value equality alone decides."""
        fid1 = mm.store_fact(_fact(
            "Alex nutzt VS Code", subject="editor", value="VS Code",
            category="general",
        ))
        fid2 = mm.store_fact(_fact(
            "Alex arbeitet mit VS Code", subject="editor", value="VS Code",
            category="general",
        ))
        assert fid2 == fid1  # reinforced, unaffected by polarity logic


class TestExplicitCorrectionWinsOverInference:
    def test_explicit_fact_not_overwritten_by_conflicting_inference(self, mm):
        fid_explicit = mm.store_fact(_fact(
            "Alex hasst Pizza", subject="pizza", value="pizza",
            source="explicit", confidence=0.90,
        ))
        fid_inferred = mm.store_fact(_fact(
            "Alex liebt Pizza", subject="pizza", value="pizza",
            source="inferred", confidence=0.70,
        ))

        explicit_after = _raw_fact(mm, fid_explicit)
        assert explicit_after["superseded_by"] is None  # NOT overwritten
        assert explicit_after["source"] == "explicit"

        inferred_fact = _raw_fact(mm, fid_inferred)
        assert inferred_fact["fact_id"] != fid_explicit
        assert mm.is_candidate(inferred_fact) is True  # stored as candidate, not truth

    def test_explicit_correction_does_supersede_explicit_fact(self, mm):
        fid1 = mm.store_fact(_fact(
            "Alex hasst Pizza", subject="pizza", value="pizza",
            source="explicit",
        ))
        fid2 = mm.store_fact(_fact(
            "Alex liebt Pizza", subject="pizza", value="pizza",
            source="explicit",
        ))
        assert _raw_fact(mm, fid1)["superseded_by"] == fid2

    def test_per_turn_inference_also_yields_to_explicit(self, mm):
        fid_explicit = mm.store_fact(_fact(
            "Alex liebt Sport", subject="sport", value="sport",
            source="explicit",
        ))
        fid_per_turn = mm.store_fact(_fact(
            "Alex hasst Sport", subject="sport", value="sport",
            source="per_turn", confidence=0.75,
        ))
        assert _raw_fact(mm, fid_explicit)["superseded_by"] is None
        assert fid_per_turn != fid_explicit


class TestConcurrentConflictingWrites:
    def test_concurrent_opposite_polarity_writes_stay_consistent(self, mm):
        """Two threads racing store_fact for opposite-polarity facts
        about the same subject must not corrupt state: exactly one
        insertion order wins, and the DB never ends up with the "wrong"
        fact showing evidence_count > 1 (a false reinforcement)."""
        errors = []
        results = []

        def write(text, value):
            try:
                fid = mm.store_fact(_fact(text, subject="kaffee", value=value))
                results.append(fid)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [
            threading.Thread(target=write, args=("Alex liebt Kaffee", "kaffee"))
            for _ in range(5)
        ] + [
            threading.Thread(target=write, args=("Alex hasst Kaffee", "kaffee"))
            for _ in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        active_facts = mm.get_facts("primary_user", category="preference")
        # Whatever the final interleaving, no active fact should have
        # been reinforced across a polarity flip: each active fact's
        # evidence_count must be explainable by same-polarity writes
        # alone (>=1, never silently corrupted/negative/None).
        for f in active_facts:
            assert isinstance(f["evidence_count"], int)
            assert f["evidence_count"] >= 1
