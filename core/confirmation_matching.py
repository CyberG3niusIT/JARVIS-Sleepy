"""Deterministic text classification for existing pending skill confirmations."""
import re


_DENIAL_WORDS = frozenset({
    "nein", "nicht", "abbrechen", "stopp", "stop", "kein", "keine",
    "keinen", "keinem", "keiner", "keines", "no", "nope", "nah",
    "cancel", "abort", "not", "don't", "dont", "never", "nevermind",
})
_DENIAL_PHRASES = ("vergiss es", "lass es")
_ACCEPTANCES = frozenset({
    "ja", "jep", "mach das", "weiter", "los", "bestätigt", "bestätigen",
    "tu es", "klar", "yes", "yeah", "yep", "yup", "go ahead", "proceed",
    "do it", "confirmed", "affirmative", "sure",
})
_POLITE_WORDS = frozenset({"bitte", "danke", "jarvis", "please", "thanks"})
_ACCEPTANCE_PATTERN = "(?:" + "|".join(re.escape(phrase) for phrase in sorted(_ACCEPTANCES)) + ")"


def parse_confirmation(text: str) -> bool | None:
    """Denial wins; only an explicit acceptance utterance returns True.

    Unknown text leaves the existing pending action untouched. Matching uses
    whole words, so names such as 'jarvis' or 'javascript' never imply 'ja'.
    """
    words = re.findall(r"\w+(?:'\w+)?", text.casefold().replace("’", "'"))
    normalized = " ".join(words)
    if set(words) & _DENIAL_WORDS or any(
        re.search(r"\b" + re.escape(phrase) + r"\b", normalized)
        for phrase in _DENIAL_PHRASES
    ):
        return False
    acceptance = " ".join(word for word in words if word not in _POLITE_WORDS)
    return True if re.fullmatch(
        _ACCEPTANCE_PATTERN + r"(?:\s+" + _ACCEPTANCE_PATTERN + ")*", acceptance
    ) else None
