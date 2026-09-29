"""Verifies task brief section 19's "Skill discovery/load test": loads
skills/personal/school and skills/system/mobility through the REAL
SkillManager.load_skill(), not a hand-rolled import, so metadata.yaml
parsing, class discovery, and initialize() all run exactly as they would
at JARVIS startup.

Uses a real Config() pointed at the repo's own config.yaml (school/mobility
sections added there) with school.db_path/mobility.db_path overridden to a
tmp_path so this test never touches /home/alex/jarvis-data.
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.config import Config
from core.skill_manager import SkillManager


class _FakeTTS:
    def speak(self, text):
        pass


class _FakeResponses:
    def acknowledgment(self):
        return "ok"

    def confirmation(self):
        return "ok"


@pytest.fixture
def skill_manager(tmp_path, monkeypatch):
    config = Config()  # real config.yaml from this checkout
    config.set("school.db_path", str(tmp_path / "school.db"))
    config.set("mobility.db_path", str(tmp_path / "mobility.db"))
    config.set("mobility.base_url", "http://127.0.0.1:8090")
    config.set("system.storage_path", str(tmp_path))
    config.set("embeddings.voice_device", "cpu")

    monkeypatch.setattr(
        "sentence_transformers.SentenceTransformer",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("embedding model disabled in unit test")
        ),
    )

    conversation = SimpleNamespace(current_user="test_user")
    manager = SkillManager(config, conversation, _FakeTTS(), _FakeResponses(), llm=None)
    return manager


def test_school_skill_loads(skill_manager):
    repo_root = Path(__file__).resolve().parent.parent.parent
    ok = skill_manager.load_skill(repo_root / "skills" / "personal" / "school")
    assert ok, "SchoolSkill failed to load via the real SkillManager"
    skill = skill_manager.get_skill("school")
    assert skill is not None
    assert skill.category == "personal"


def test_mobility_skill_loads(skill_manager):
    repo_root = Path(__file__).resolve().parent.parent.parent
    ok = skill_manager.load_skill(repo_root / "skills" / "system" / "mobility")
    assert ok, "MobilitySkill failed to load via the real SkillManager"
    skill = skill_manager.get_skill("mobility")
    assert skill is not None
    assert skill.category == "system"


def test_both_skills_load_together_without_intent_pattern_conflicts(skill_manager):
    repo_root = Path(__file__).resolve().parent.parent.parent
    assert skill_manager.load_skill(repo_root / "skills" / "personal" / "school")
    assert skill_manager.load_skill(repo_root / "skills" / "system" / "mobility")
    assert set(skill_manager.list_skills()) >= {"school", "mobility"}


@pytest.mark.parametrize("question,expected", [
    ("Wann hat TestkindAlpha heute aus?", "school"),
    ("Muss ich TestkindBeta heute abholen?", "school"),
    ("Wann muss ich los, um TestkindAlpha abzuholen?", "school"),
    ("Wann muss ich los?", "mobility"),
])
def test_school_mobility_intent_overlap(skill_manager, question, expected):
    """Use the real loader and matcher with all available existing skills."""
    skill_manager.load_all_skills()
    match = skill_manager.match_intent(question)
    assert match is not None
    assert match[0] == expected
    assert skill_manager._last_match_info["layer"] == "exact"


@pytest.mark.parametrize("question", [
    "Erinnere mich daran, TestkindAlpha heute abzuholen",
    "Wie ist das Wetter heute?",
    "Wann fÃ¤hrt der Bus?",
])
def test_other_intents_do_not_execute_school_or_mobility(skill_manager, question):
    root = Path(__file__).resolve().parents[2]
    for path in ("personal/school", "system/mobility"):
        assert skill_manager.load_skill(root / "skills" / path)
    assert skill_manager.execute_intent(question) is None
