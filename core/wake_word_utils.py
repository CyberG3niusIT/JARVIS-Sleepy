"""Pure wake-word matching and command extraction helpers."""

from difflib import SequenceMatcher
import re

WAKE_ALIASES = frozenset({
    "jarvis", "jarwis", "jarwiss", "charvis", "charwis", "chauvis",
    "chauwis", "scharvis", "djarvis", "dscharvis", "tscharvis",
})
_TOKEN = re.compile(r"[\w']+", re.UNICODE)


def find_wake_word(text: str, wake_word: str, threshold: float = 0.80):
    """Return the first fuzzy wake token span and similarity, if found."""
    aliases = WAKE_ALIASES | {wake_word.casefold()}
    for match in _TOKEN.finditer(text):
        token = match.group().casefold()
        score = max(SequenceMatcher(None, alias, token).ratio() for alias in aliases)
        if score >= threshold:
            return match.start(), match.end(), match.group(), score
    return None


def strip_wake_word(text: str, wake_word: str) -> str:
    """Remove one matched wake token and its vocative commas."""
    found = find_wake_word(text, wake_word)
    if not found:
        return text.strip()
    start, end, _, _ = found
    before = re.sub(r",\s*$", "", text[:start])
    after = re.sub(r"^\s*,", "", text[end:])
    result = re.sub(r"\s+", " ", f"{before} {after}").strip()
    return result.strip(" \t\r\n.,!?;:")
