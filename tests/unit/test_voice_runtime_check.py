"""Unit tests for scripts/check_chatterbox_runtime.py."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.check_chatterbox_runtime import compare_contract, expected_contract, parse_env_file


def _env():
    return {
        "CHATTERBOX_LANGUAGE": "de",
        "CHATTERBOX_TEMPO": "0.89",
        "CHATTERBOX_EXAGGERATION": "0.5",
        "CHATTERBOX_CFG_WEIGHT": "0.5",
        "CHATTERBOX_TEMPERATURE": "0.8",
        "CHATTERBOX_REPETITION_PENALTY": "1.2",
        "CHATTERBOX_MIN_P": "0.05",
        "CHATTERBOX_TOP_P": "1.0",
        "CHATTERBOX_AUDIO_PROMPT_PATH": "/tmp/reference.wav",
        "CHATTERBOX_AUDIO_PROMPT_SHA256": "abc123",
    }


def test_expected_contract_maps_runtime_env():
    contract = expected_contract(_env())
    assert contract["language"] == "de"
    assert contract["tempo"] == 0.89
    assert contract["audio_prompt_sha256"] == "abc123"


def test_compare_contract_accepts_identical_values():
    expected = expected_contract(_env())
    assert compare_contract(dict(expected), expected) == []


def test_compare_contract_reports_voice_drift():
    expected = expected_contract(_env())
    actual = dict(expected)
    actual["tempo"] = 0.91
    actual["audio_prompt_sha256"] = "wrong"
    errors = compare_contract(actual, expected)
    assert any("tempo" in e for e in errors)
    assert any("audio_prompt_sha256" in e for e in errors)


def test_parse_env_file_ignores_comments_and_blank_lines(tmp_path: Path):
    path = tmp_path / "chatterbox.env"
    path.write_text("# comment\n\nA=1\nB='two'\n", encoding="utf-8")
    assert parse_env_file(path) == {"A": "1", "B": "two"}
