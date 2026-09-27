"""Pure, side-effect-free helpers that decide where a direct-audio turn goes.

Direct audio (Gemma hears the audio, no tools) is the normal path. The parallel
STT transcript may only DIVERT a turn to the text pipeline when it clearly needs
tools/skills/canned handling, or when it is a bare wake word (greeting).

Nothing here routes, executes skills or touches router/conversation state.
"""

from __future__ import annotations

import re
from typing import Optional

DIRECT = "direct"
TEXT = "text"
GREETING = "greeting"

_NON_WORD = re.compile(r"[\W_]+", re.UNICODE)

# German + English tool/skill keywords (kept in sync with core.tool_gate).
_KEYWORDS = [
    (r"wie\s+sp(?:ä|ae)t", "time"),
    (r"uhrzeit|wieviel\s+uhr|wie\s+viel\s+uhr|what\s+time", "time"),
    (r"welche[nrs]?\s+(?:tag|datum)|datum\b|today'?s\s+date", "date"),
    (r"wetter|vorhersage|regnet|temperatur\s+in|forecast|weather", "weather"),
    (r"erinner\w*|remind\w*|timer\b|wecker|alarm\b", "reminder"),
    (r"termin(?:e|en)?\b|kalender|calendar|meeting", "calendar"),
    (r"such(?:e|en)?\s+(?:nach|im|mir|mal|bitte)|google\b|recherchier\w*|search\s+for|look\s+up", "search"),
    (r"nachrichten|neuigkeiten|schlagzeilen|headlines|\bnews\b", "news"),
    (r"(?:öffne|oeffne|starte|schließe|schliesse|beende)\s+\w+|(?:open|launch|close|quit)\s+\w+", "app"),
    (r"lautst(?:ä|ae)rke|leiser|lauter|stumm|volume|\bmute\b", "volume"),
    (r"screenshot|bildschirm|webcam|kamera", "screen"),
    (r"merk\s+dir|merke\s+dir|vergiss\b|vergessen\s+sie|erinnerst\s+du\s+dich|what\s+do\s+you\s+remember", "memory"),
    (r"experte[n]?\b|expert\b", "expert"),
    (r"cpu|\bram\b|gpu|festplatte|speicherplatz|disk\s+space|systemstatus", "system"),
]
_KEYWORD_PATTERNS = [(re.compile(rf"(?<!\w)(?:{p})", re.IGNORECASE | re.UNICODE), name)
                     for p, name in _KEYWORDS]


def is_wake_only(text: Optional[str], wake_word: str) -> bool:
    """True when the utterance is only the wake word (plus punctuation/noise)."""
    from core.wake_word_utils import find_wake_word, strip_wake_word
    raw = (text or "").strip()
    if not raw or not wake_word:
        return False
    if not find_wake_word(raw, wake_word):
        return False
    rest = strip_wake_word(raw, wake_word)
    return not _NON_WORD.sub("", rest)


def keyword_text_path_reason(command: Optional[str]) -> Optional[str]:
    """Return ``"keyword:<name>"`` if the command clearly needs a tool/skill."""
    text = (command or "").strip()
    if not text:
        return None
    for pattern, name in _KEYWORD_PATTERNS:
        if pattern.search(text):
            return f"keyword:{name}"
    return None
