"""The read-only API skips semantic execution models; command-serving web keeps them."""

from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("desktop_mode", [True, False])
def test_init_selects_embeddings_only_for_command_serving_process(monkeypatch, desktop_mode):
    import jarvis_web

    config = SimpleNamespace(get=lambda key, default=None: default)
    monkeypatch.setattr(jarvis_web, "ConversationManager", lambda cfg: SimpleNamespace())
    monkeypatch.setattr(jarvis_web, "LLMRouter", lambda cfg: object())
    captured = {}

    class ReachedSkillManager(Exception):
        pass

    def capture_skill_manager(*args, **kwargs):
        captured.update(kwargs)
        raise ReachedSkillManager

    monkeypatch.setattr(jarvis_web, "SkillManager", capture_skill_manager)
    with pytest.raises(ReachedSkillManager):
        jarvis_web.init_components(config, None, desktop_mode=desktop_mode)
    assert captured["preload_embeddings"] is (not desktop_mode)
