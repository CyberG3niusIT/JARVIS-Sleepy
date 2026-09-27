#!/usr/bin/env python3
"""Idempotent migration for Sleepy conversational voice mode."""

from __future__ import annotations

import py_compile
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TTS = ROOT / "core" / "tts.py"
PIPELINE = ROOT / "core" / "pipeline.py"
CONFIG = ROOT / "config.yaml"


def backup(path: Path) -> None:
    dst = path.with_suffix(path.suffix + ".bak-voice-conversation")
    if not dst.exists():
        shutil.copy2(path, dst)


def patch_tts() -> bool:
    text = TTS.read_text(encoding="utf-8")
    original = text

    legacy = '''        # Ack state must exist for every TTS backend.\n        # Kokoro fills the cache later; Piper intentionally leaves it empty.\n        self._ack_cache = {}\n        self._ack_played = False\n\n'''
    text = text.replace(legacy, "")

    canonical = '''        # Ack state exists for every TTS backend. Kokoro fills this cache later;\n        # Piper intentionally leaves it empty. This prevents speak_ack() from\n        # crashing when Piper is the active German voice engine.\n        self._ack_cache: Dict[str, tuple[bytes, str]] = {}\n        self._ack_played = False\n'''

    if canonical not in text:
        needle = '''        # Track whether speak() was called (for caller detection)\n        self._spoke = False\n'''
        if needle not in text:
            raise RuntimeError("TTS patch point not found")
        text = text.replace(needle, needle + "\n" + canonical, 1)

    if text != original:
        backup(TTS)
        TTS.write_text(text, encoding="utf-8")
        return True
    return False


def patch_pipeline() -> bool:
    text = PIPELINE.read_text(encoding="utf-8")
    original = text

    # Repair an earlier over-escaped variant if present.
    text = text.replace(
        'r"\\\\bjarvis(?:\\\\s+(?:hey\\\\s+)?jarvis)+\\\\b"',
        'r"\\bjarvis(?:\\s+(?:hey\\s+)?jarvis)+\\b"',
    )
    text = text.replace(
        'r"^\\\\s*(?:hey|hi|hallo)\\\\s+jarvis\\\\b"',
        'r"^\\s*(?:hey|hi|hallo)\\s+jarvis\\b"',
    )

    marker = "Normalize common wake-word forms."
    if marker not in text:
        needle = '''            corrected_text = text.replace(matched_word, self.wake_word)\n'''
        if needle not in text:
            raise RuntimeError("Pipeline wake-word patch point not found")
        block = '''\n            # Normalize common wake-word forms.\n            # Qwen hotword bias can occasionally duplicate the wake phrase,\n            # e.g. "jarvis hey jarvis öffne ...".\n            corrected_text = re.sub(\n                r"\\bjarvis(?:\\s+(?:hey\\s+)?jarvis)+\\b",\n                "jarvis",\n                corrected_text,\n                flags=re.IGNORECASE,\n            )\n\n            # "Hey Jarvis ..." is an invocation, not a command containing "hey".\n            corrected_text = re.sub(\n                r"^\\s*(?:hey|hi|hallo)\\s+jarvis\\b",\n                "jarvis",\n                corrected_text,\n                flags=re.IGNORECASE,\n            )\n'''
        text = text.replace(needle, needle + block, 1)

    if text != original:
        backup(PIPELINE)
        PIPELINE.write_text(text, encoding="utf-8")
        return True
    return False


def set_line(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Config setting not found or ambiguous: {label}")
    return updated


def patch_config() -> bool:
    text = CONFIG.read_text(encoding="utf-8")
    original = text
    text = set_line(text, r"^  speech_frames_threshold:\s*\d+\s*$", "  speech_frames_threshold: 10", "vad.speech_frames_threshold")
    text = set_line(text, r"^  silence_frames_threshold:\s*\d+\s*$", "  silence_frames_threshold: 25", "vad.silence_frames_threshold")
    text = set_line(text, r"^  buffer_duration:\s*[0-9.]+\s*$", "  buffer_duration: 1.0", "vad.buffer_duration")
    text = set_line(text, r'^    hotwords:\s*"[^"]*"\s*$', '    hotwords: "Jarvis"', "stt.qwen3.hotwords")
    text = set_line(text, r"^    default_duration:\s*[0-9.]+\s*$", "    default_duration: 8.0", "conversation.follow_up_window.default_duration")
    text = set_line(text, r"^    extended_duration:\s*[0-9.]+\s*$", "    extended_duration: 12.0", "conversation.follow_up_window.extended_duration")

    if text != original:
        backup(CONFIG)
        CONFIG.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = []
    if patch_tts():
        changed.append("core/tts.py")
    if patch_pipeline():
        changed.append("core/pipeline.py")
    if patch_config():
        changed.append("config.yaml")

    py_compile.compile(str(TTS), doraise=True)
    py_compile.compile(str(PIPELINE), doraise=True)

    print("Sleepy conversational voice mode configured.")
    print("Changed: " + (", ".join(changed) if changed else "nothing"))
    print("Syntax check: OK")
    print("Voice settings: VAD 10/25, prebuffer 1.0s, hotword Jarvis, follow-up 8/12s")
    print("Start: python jarvis_console.py --speech")


if __name__ == "__main__":
    main()
