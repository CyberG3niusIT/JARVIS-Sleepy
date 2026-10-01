"""Exercise actual startup methods with TTS spies and no hardware imports."""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from core import persona

ROOT = Path(__file__).resolve().parents[2]


def runtime_method(name):
    tree = ast.parse((ROOT / "jarvis_continuous.py").read_text(encoding="utf-8"))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "JarvisContinuous")
    method = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)
    env = {"get_honorific": lambda: "Sir", "Path": Path}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "jarvis_continuous.py", "exec"), env)
    return env[name]


@pytest.mark.parametrize("mic_ok", [True, False])
def test_real_startup_and_microphone_announcements_are_german(monkeypatch, mic_ok, capsys):
    watcher = ModuleType("core.privacy_control_watcher")
    watcher.PrivacyControlWatcher = Mock(return_value=Mock())
    monkeypatch.setitem(sys.modules, watcher.__name__, watcher)
    runtime = Mock()
    runtime.event_mode = False
    runtime.wake_word = "jarvis"
    runtime.listener.start_with_retry.return_value = mic_ok
    # End the real run loop immediately, without opening devices or a worker.
    timer = Mock()
    timer.sleep.side_effect = KeyboardInterrupt
    method = runtime_method("run")
    method.__globals__["time"] = timer
    method(runtime)
    runtime.listener._on_mic_state_change(True)
    runtime.listener._on_mic_state_change(False)
    spoken = [call.args[0] for call in runtime.tts.speak.call_args_list]
    expected = [
        "Mikrofon wieder verbunden, Sir. Die Spracheingabe ist aktiv.",
        "Mikrofon getrennt, Sir. Die Spracheingabe ist pausiert.",
    ]
    if not mic_ok:
        expected.insert(
            0,
            "Kein Mikrofon erkannt, Sir. Ich arbeite ohne Spracheingabe weiter. "
            "Ich melde mich, sobald das Mikrofon verfügbar ist.",
        )
    assert spoken == expected
    console = capsys.readouterr().out
    assert "Aktivierungswort:" in console
    assert "Zum Beenden Strg+C drücken." in console


@pytest.mark.parametrize("issue_count", [0, 1, 2])
def test_real_startup_health_check_speaks_german(monkeypatch, issue_count):
    health = ModuleType("core.health_check")
    health.register_coordinator = Mock()
    health.get_full_health = Mock(return_value={"local": [{"status": "red"}] * issue_count})
    health.format_visual_report = Mock(return_value="Diagnose")
    monkeypatch.setitem(sys.modules, health.__name__, health)
    runtime = Mock()
    runtime_method("_run_startup_health_check")(runtime)
    if issue_count == 0:
        runtime.tts.speak.assert_not_called()
    else:
        result = runtime.tts.speak.call_args.args[0]
        assert "bei der Initialisierung" in result
        assert "Ich zeige Ihnen den Bericht." in result
        assert ("ein Problem" if issue_count == 1 else "2 Probleme") in result


@pytest.mark.parametrize(
    "prompt",
    [persona.system_prompt, persona.system_prompt_guest, persona.system_prompt_brief, persona.system_prompt_minimal],
)
def test_every_persona_prompt_contains_current_request_language_invariant(prompt):
    assert persona.DEFAULT_LANGUAGE == "de-DE"
    assert persona.OWNER_LANGUAGE_RULE in prompt()
    assert "in der aktuellen Anfrage" in prompt()
    assert "Frühere Sprachwünsche" in prompt()


@pytest.mark.parametrize("category", list(persona._POOLS))
def test_effective_persona_pools_have_no_known_english_legacy_responses(category):
    # This is a regression audit of known literals, not a runtime language detector.
    for entry in persona.pool(category):
        phrase = entry[0] if isinstance(entry, tuple) else entry
        assert not phrase.startswith(
            (
                "Of course",
                "I'll",
                "I'm",
                "Shall I",
                "Good morning",
                "Very well",
                "Welcome",
                "Let me",
                "Sorry",
                "Here is",
            )
        )


def test_effective_tts_cache_uses_german_persona_content():
    from core.tts import TextToSpeech

    assert "Einen Moment." in [phrase for phrase, _ in persona.pool_tagged("ack_cache")]
    assert "Guten Morgen, {honorific}." in TextToSpeech._CAL_L0_TEMPLATES
    assert not any(
        text.startswith(("Welcome", "Of course", "I'll", "Good morning")) for text in TextToSpeech._CAL_L0_TEMPLATES
    )


def test_contextual_ack_actual_generate_call_has_german_instruction():
    llm = Mock()
    llm.generate.return_value = "Ich prüfe das."
    assert persona.generate_contextual_ack("Check the weather", llm) == "Ich prüfe das."
    prompt = llm.generate.call_args.args[0]
    assert "kurzen deutschen Bestätigungssatz" in prompt
    assert "Check the weather" in prompt
    llm.generate.assert_called_once()


def test_response_library_effective_owner_fallbacks_are_german():
    from core.responses import ResponseLibrary

    library = ResponseLibrary()
    for category, pool in library.responses.items():
        assert pool, category
        assert not any(
            text.startswith(("I'm", "Sorry", "Good morning", "Welcome", "Of course")) for text in pool
        ), category
