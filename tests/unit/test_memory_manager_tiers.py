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
          source="explicit", confidence=0.90, user_id="primary_user",
          value=None):
    return {
        "user_id": user_id,
        "category": category,
        "subject": subject,
        "content": content,
        "value": value,
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


class TestValueBasedReinforcementVsSupersede:
    """The core problem this session was asked to solve: a paraphrase of
    the same fact must reinforce, a real change of the same attribute
    must supersede. Plain text similarity gets this backwards (see
    docs/ARCHITECTURE.md §5c) — comparing the extracted `value` instead
    of the whole sentence is what actually works."""

    def test_paraphrase_with_same_value_reinforces(self, mm):
        fid1 = mm.store_fact(_fact(
            "the user often uses VS Code for development",
            subject="editor", value="VS Code",
            source="inferred", confidence=0.70,
        ))
        fid2 = mm.store_fact(_fact(
            "the user mostly works with VS Code for coding tasks",
            subject="editor", value="VS Code",
            source="inferred", confidence=0.70,
        ))
        assert fid1 == fid2
        reinforced = mm.get_fact_by_id(fid1)
        assert reinforced["evidence_count"] == 2

    def test_different_value_supersedes_despite_similar_wording(self, mm):
        old_id = mm.store_fact(_fact(
            "the user's favorite editor is VS Code",
            subject="editor", value="VS Code",
        ))
        new_id = mm.store_fact(_fact(
            "the user's favorite editor is Cursor",
            subject="editor", value="Cursor",
        ))
        assert old_id != new_id
        assert mm.get_fact_by_id(old_id) is None
        active = mm.get_facts(category="preference")
        assert any(f["value"] == "Cursor" for f in active)
        assert not any(f["value"] == "VS Code" for f in active)

    def test_missing_value_falls_back_to_content_comparison(self, mm):
        # No value on either side — must behave exactly like before this
        # session's change (exact content match -> reinforce).
        fid1 = mm.store_fact(_fact("the user loves the band Tool", subject="music"))
        fid2 = mm.store_fact(_fact("the user loves the band Tool", subject="music"))
        assert fid1 == fid2


class TestSensitiveRiskGate:
    def test_inferred_health_fact_capped_below_candidate_threshold(self, mm):
        fid = mm.store_fact(_fact(
            "the user mentioned feeling anxious lately",
            subject="mood", category="health",
            source="inferred", confidence=0.90,  # extractor over-confident
        ))
        fact = mm.get_fact_by_id(fid)
        assert fact["confidence"] <= mm._SENSITIVE_CAP_CONFIDENCE
        assert mm.is_candidate(fact) is True

    def test_sensitive_fact_never_promoted_by_reinforcement(self, mm):
        fact = _fact(
            "the user mentioned feeling anxious about work",
            subject="mood", category="health",
            source="inferred", confidence=0.70,
        )
        for _ in range(10):
            fid = mm.store_fact(dict(fact))
        result = mm.get_fact_by_id(fid)
        assert result["confidence"] <= mm._SENSITIVE_CAP_CONFIDENCE
        assert mm.is_candidate(result) is True

    def test_explicit_sensitive_fact_not_capped(self, mm):
        # The user stating something explicitly is categorically
        # different from the system inferring it — must NOT be capped.
        fid = mm.store_fact(_fact(
            "the user has diagnosed anxiety",
            subject="health_condition", category="health",
            source="explicit", confidence=0.90,
        ))
        fact = mm.get_fact_by_id(fid)
        assert fact["confidence"] == 0.90
        assert mm.is_candidate(fact) is False

    def test_keyword_based_sensitivity_outside_health_category(self, mm):
        # A politically/financially sensitive fact filed under "general"
        # or "opinion" by the extractor must still be caught.
        fid = mm.store_fact(_fact(
            "the user mentioned having significant debt",
            subject="finances", category="general",
            source="inferred", confidence=0.70,
        ))
        fact = mm.get_fact_by_id(fid)
        assert fact["confidence"] <= mm._SENSITIVE_CAP_CONFIDENCE


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


class TestEnglishForgetNegation:
    """Reviewer-found bug: "don't forget that X" (a FACT_REQUEST — the
    opposite meaning) was matching FORGET_PATTERNS via unanchored
    re.search, so JARVIS tried to delete X instead of remembering it."""

    def test_dont_forget_that_is_not_a_forget_request(self, mm):
        assert mm.is_forget_request("don't forget that I love pizza") is False

    def test_do_not_forget_the_is_not_a_forget_request(self, mm):
        assert mm.is_forget_request("do not forget the meeting tomorrow") is False

    def test_plain_forget_that_is_still_a_forget_request(self, mm):
        assert mm.is_forget_request("forget that I mentioned coffee") is True

    def test_forget_the_fact_about_still_detected(self, mm):
        assert mm.is_forget_request("please forget the fact about my old job") is True


class TestCategoryScopedDedup:
    """Reviewer-found bug: _find_similar_fact() matched purely on subject
    with no category constraint, so two unrelated facts that happen to
    share a generic subject (e.g. "mutter") could silently supersede
    each other."""

    def test_same_subject_different_category_does_not_supersede(self, mm):
        id1 = mm.store_fact(_fact(
            "the user's mother's name is Petra",
            subject="mutter", category="relationship",
            value="Petra",
        ))
        id2 = mm.store_fact(_fact(
            "the user's mother works as a teacher",
            subject="mutter", category="work",
            value="teacher",
        ))
        assert id1 != id2
        # Both must still be active — different categories, unrelated facts.
        assert mm.get_fact_by_id(id1) is not None
        assert mm.get_fact_by_id(id2) is not None

    def test_same_subject_same_category_still_supersedes(self, mm):
        id1 = mm.store_fact(_fact(
            "the user's favorite editor is VS Code",
            subject="editor", category="preference", value="VS Code",
        ))
        id2 = mm.store_fact(_fact(
            "the user's favorite editor is Cursor",
            subject="editor", category="preference", value="Cursor",
        ))
        assert id1 != id2
        assert mm.get_fact_by_id(id1) is None  # correctly superseded


class TestStoreFactConcurrency:
    """Reviewer-found TOCTOU race: read (_find_similar_fact) and the
    later write happened in separate lock acquisitions, so two threads
    calling store_fact() for the same fact concurrently could both see
    "no existing fact" and insert duplicates, or both reinforce from the
    same stale snapshot and lose an observation. store_fact() now wraps
    the whole read-decide-write sequence in one RLock acquisition."""

    def test_concurrent_identical_facts_produce_no_duplicate(self, mm):
        import threading

        fact = _fact(
            "the user often uses VS Code for development",
            subject="editor_usage", value="VS Code",
            source="inferred", confidence=0.70,
        )
        results = []

        def worker():
            results.append(mm.store_fact(dict(fact)))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        active = mm.get_facts(category="preference")
        matching = [f for f in active if f["subject"] == "editor_usage"]
        assert len(matching) == 1, "concurrent identical facts created duplicates"
        assert matching[0]["evidence_count"] == 8, (
            f"expected all 8 concurrent observations counted, got "
            f"{matching[0]['evidence_count']}"
        )


class TestGermanCommands:
    def test_german_transparency_query_detected(self, mm):
        assert mm.is_transparency_request("was weißt du über mich") is True

    def test_german_recall_query_detected(self, mm):
        assert mm.is_recall_query("erinnerst du dich an mein Projekt") is True
        assert mm.is_recall_query("was hatten wir über Docker besprochen") is True

    def test_german_forget_request_detected(self, mm):
        assert mm.is_forget_request("lösche die Erinnerung an meinen alten Job") is True

    def test_german_forget_with_negation_not_misdetected(self, mm):
        # "vergiss nicht" means the OPPOSITE (remember) — must not be
        # treated as a forget request.
        assert mm.is_forget_request("vergiss nicht, dass ich Diabetiker bin") is False

    def test_german_why_query_detected(self, mm):
        assert mm.is_why_query("warum glaubst du, dass ich VS Code mag") is True

    def test_german_fact_request_detected(self, mm):
        assert mm.is_fact_request("merke dir, dass ich Vegetarier bin") is True


class TestGermanOutputRendering:
    def test_transparency_output_is_german(self, mm):
        mm.store_fact(_fact(
            "the user's favorite editor is VS Code",
            subject="editor", value="VS Code",
        ))
        result = mm.handle_transparency("was weißt du über mich")
        assert "I know" not in result
        assert "Ich weiß" in result or "Ich habe" in result

    def test_forget_output_is_german(self, mm):
        mm.store_fact(_fact(
            "the user's favorite editor is VS Code",
            subject="editor", value="VS Code",
        ))
        result = mm.handle_forget("lösche die Erinnerung an editor")
        assert "I found" not in result
        assert "Shall I" not in result
        assert "gefunden" in result

    def test_render_fact_de_prefers_value_over_english_content(self, mm):
        fact = _fact(
            "the user's favorite editor is VS Code",
            subject="editor", value="VS Code",
        )
        rendered = mm.render_fact_de(fact)
        assert "the user's" not in rendered
        assert "VS Code" in rendered

    def test_render_fact_de_falls_back_to_content_without_value(self, mm):
        fact = _fact("the user loves the band Tool", subject="music", value=None)
        rendered = mm.render_fact_de(fact)
        assert rendered == "the user loves the band Tool"


class TestWhyQuery:
    def test_why_explains_explicit_fact(self, mm):
        mm.store_fact(_fact(
            "the user's favorite editor is VS Code",
            subject="editor", value="VS Code", source="explicit",
        ))
        result = mm.handle_why("warum glaubst du, dass ich VS Code mag")
        assert "selbst" in result

    def test_why_explains_inferred_fact_with_evidence_count(self, mm):
        fact = _fact(
            "the user often uses VS Code for development",
            subject="editor_usage", value="VS Code",
            source="inferred", confidence=0.70,
        )
        for _ in range(3):
            mm.store_fact(dict(fact))
        result = mm.handle_why("warum glaubst du, dass ich VS Code benutze")
        assert "Vermutung" in result

    def test_why_with_no_matching_fact(self, mm):
        result = mm.handle_why("warum glaubst du, dass ich Klavier spiele")
        assert "keine gespeicherte Grundlage" in result


class TestCandidateLabelingInPromptContext:
    """§16: the LLM must never see a candidate/inferred observation with
    the same authority as a confirmed fact in the injected context."""

    def test_confirmed_and_candidate_facts_in_separate_sections(self, mm):
        mm.store_fact(_fact(
            "the user's favorite editor is VS Code",
            subject="editor", value="VS Code", source="explicit",
        ))
        mm.store_fact(_fact(
            "the user often mentions feeling stressed at work",
            subject="mood", value=None, source="inferred", confidence=0.70,
        ))
        block = mm.get_full_user_context()
        assert "WHAT YOU KNOW ABOUT THE USER" in block
        assert "UNCONFIRMED OBSERVATIONS" in block
        confirmed_idx = block.index("WHAT YOU KNOW")
        candidate_idx = block.index("UNCONFIRMED OBSERVATIONS")
        assert block[confirmed_idx:candidate_idx].find("VS Code") != -1
        assert block[candidate_idx:].find("stressed") != -1

    def test_only_confirmed_facts_no_candidate_section(self, mm):
        mm.store_fact(_fact(
            "the user's favorite editor is VS Code",
            subject="editor", value="VS Code", source="explicit",
        ))
        block = mm.get_full_user_context()
        assert "UNCONFIRMED OBSERVATIONS" not in block


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
