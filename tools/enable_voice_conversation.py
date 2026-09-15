#!/usr/bin/env python3
"""Enable and harden conversational voice mode for Sleepy JARVIS.

Idempotent local migration for the current Windows/WSL2 build.
It fixes Piper ack state, improves live speech segmentation, reduces Qwen hotword
over-biasing, and makes the follow-up conversation window long enough for
natural back-and-forth speech.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TTS = ROOT / "core" / "tts.py"
PIPELINE = ROOT / "core" / "pipeline.py"
CONFIG = ROOT / "config.yaml"


def backup(path: Path) -> None:
    target = path.with_suffix(path.suffix + ".bak-voice-conversation")
    if not target.exists():
        shutil.copy2(path, target)


def patch_tts() -> bool:
    text = TTS.read_text(encoding="utf-8")
    if "Ack state exists for every TTS backend" in text:
        return False

    needle = '''        # Track whether speak() was called (for caller detection)\n        self._spoke = False\n'''
    replacement = '''        # Track whether speak() was called (for caller detection)\n        self._spoke = False\n\n        # Ack state exists for every TTS backend. Kokoro fills this cache later;\n        # Piper intentionally leaves it empty. This prevents speak_ack() from\n        # crashing when Piper is the active German voice engine.\n        self._ack_cache: Dict[str, tuple[bytes, str]] = {}\n        self._ack_played = False\n'''

    if needle not in text:
        raise RuntimeError("TTS patch point not found")

    backup(TTS)
    TTS.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
    return True


def patch_pipeline() -> bool:
    text = PIPELINE.read_text(encoding="utf-8")
    if "SLEEPY_WAKE_NORMALIZATION" in text:
        return False

    needle = '''            corrected_text = text.replace(matched_word, self.wake_word)\n            self.logger.info(f"Corrected: '{text}' → '{corrected_text}'")\n'''
    replacement = '''            corrected_text = text.replace(matched_word, self.wake_word)\n\n            # SLEEPY_WAKE_NORMALIZATION\n            # Qwen hotword bias can occasionally duplicate the invocation, for\n            # example "jarvis hey jarvis öffne ...". Normalize the invocation\n            # before command extraction so "hey" never becomes the command.\n            corrected_text = re.sub(\n                r"\\bjarvis(?:\\s+(?:hey\\s+)?jarvis)+\\b",\n                "jarvis",\n                corrected_text,\n                flags=re.IGNORECASE,\n            )\n            corrected_text = re.sub(\n                r"^\\s*(?:hey|hi|hallo)\\s+jarvis\\b",\n                "jarvis",\n                corrected_text,\n                flags=re.IGNORECASE,\n            )\n\n            self.logger.info(f"Corrected: '{text}' → '{corrected_text}'")\n'''

    if needle not in text:
        raise RuntimeError("Pipeline wake-word patch point not found")

    backup(PIPELINE)
    PIPELINE.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
    return True


def replace_setting(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Config setting not found or ambiguous: {label}")
    return updated


def patch_config() -> bool:
    text = CONFIG.read_text(encoding="utf-8")
    original = text

    text = replace_setting(
        text,
        r"^  speech_frames_threshold:\s*\d+\s*$",
        "  speech_frames_threshold: 10",
        "vad.speech_frames_threshold",
    )
    text = replace_setting(
        text,
        r"^  silence_frames_threshold:\s*\d+\s*$",
        "  silence_frames_threshold: 25",
        "vad.silence_frames_threshold",
    )
    text = replace_setting(
        text,
        r"^  buffer_duration:\s*[0-9.]+\s*$",
        "  buffer_duration: 1.0",
        "vad.buffer_duration",
    )
    text = replace_setting(
        text,
        r'^    hotwords:\s*"[^"]*"\s*$',
        '    hotwords: "Jarvis"',
        "stt.qwen3.hotwords",
    )
    text = replace_setting(
        text,
        r"^    default_duration:\s*[0-9.]+\s*$",
        "    default_duration: 8.0",
        "conversation.follow_up_window.default_duration",
    )
    text = replace_setting(
        text,
        r"^    extended_duration:\s*[0-9.]+\s*$",
        "    extended_duration: 12.0",
        "conversation.follow_up_window.extended_duration",
    )

    if text == original:
        return False

    backup(CONFIG)
    CONFIG.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = []
    if patch_tts():
        changed.append("core/tts.py")
    if patch_pipeline():
        changed.append("core/pipeline.py")
    if patch_config():
        changed.append("config.yaml")

    print("Sleepy conversational voice mode configured.")
    if changed:
        print("Changed:")
        for item in changed:
            print(f"  - {item}")
    else:
        print("No changes needed. Migration was already applied.")

    print("\nEffective voice settings:")
    print("  - Piper ack crash fixed")
    print("  - VAD speech start: 10 frames")
    print("  - VAD speech end: 25 silent frames")
    print("  - pre-speech buffer: 1.0 s")
    print('  - Qwen hotword bias: "Jarvis"')
    print("  - follow-up window: 8 s")
    print("  - extended follow-up window: 12 s")
    print("\nStart with: python jarvis_console.py --speech")


if __name__ == "__main__":
    main()
