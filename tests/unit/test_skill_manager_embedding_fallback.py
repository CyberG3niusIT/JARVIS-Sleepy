"""The skill manager remains usable when optional embeddings cannot load."""

import builtins
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

from core.config import Config
from core.skill_manager import SkillManager


def test_readonly_skill_catalog_never_imports_embedding_runtime(monkeypatch):
    config = Config()
    original_import = builtins.__import__

    def reject_embedding_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise AssertionError("read-only catalog must not load a routing model")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_embedding_import)
    manager = SkillManager(config, SimpleNamespace(), None, None, None,
                           preload_embeddings=False)
    assert manager._embedding_model is None
    assert manager.discover_skills()


def test_embedding_fallback_is_used_when_sentence_transformers_is_unavailable(monkeypatch):
    config = Config()
    config.set("embeddings.voice_device", "cpu")
    original_import = builtins.__import__

    def import_without_sentence_transformers(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("optional embedding runtime unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_sentence_transformers)

    manager = SkillManager(config, SimpleNamespace(), None, None, None)

    assert manager._embedding_model is None
    assert manager._match_semantic_intents("an unrelated request") is None
    skill = SimpleNamespace(semantic_intents={})
    assert manager._disambiguate_suffix(skill, "sample", [], "request", {}, "keyword") is None
    assert manager._try_keyword_semantic_fallback(skill, "sample", "request", {}) is None
