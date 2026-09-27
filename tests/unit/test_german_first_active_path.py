"""German-first regression guard for the active spoken-response pools.

JARVIS speaks German (system.language: de-DE). These pools are the
highest-frequency spoken content — CAL-L0 cache templates (core/tts.py)
and persona response pools (core/persona.py) — and used to contain
untranslated English filler ("Good morning, sir.", "Welcome back.",
"You're welcome.", ...). This test fails if any of those specific,
previously-confirmed English phrases reappear in the active pools, so a
future upstream sync (core/tts.py and core/persona.py both receive
"Sync:" commits from the InterGenJLU/jarvis upstream) can't silently
reintroduce them — see docs/ARCHITECTURE.md section on German-first.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

# Confirmed-banned literal English filler phrases (or distinctive substrings)
# that were found in the active German runtime path before this session's
# migration. Substring match, case-sensitive (German text may legitimately
# contain "Sir" as a stylistic honorific — these are full stock phrases,
# not the honorific alone).
BANNED_ENGLISH_PHRASES = [
    "Good morning,",
    "Good afternoon,",
    "Good evening,",
    "Welcome back,",
    "At your service,",
    "Standing by,",
    "You're welcome,",
    "My pleasure,",
    "How can I help,",
    "What do you need,",
    "Take care,",
    "Goodnight,",
    "Sleep well,",
    "Understood, {honorific}. I'll be here",
    "Sehr wohl, {honorific}.",  # stiff butler-calque, explicitly avoided
]


def _assert_no_banned_phrases(phrases, label):
    offenders = []
    for phrase in phrases:
        for banned in BANNED_ENGLISH_PHRASES:
            if banned in phrase:
                offenders.append((phrase, banned))
    assert not offenders, f"{label} contains banned English/butler-calque phrases: {offenders}"


class TestCalL0TemplatesAreGerman:
    def test_no_banned_english_phrases(self):
        from core.tts import TextToSpeech
        _assert_no_banned_phrases(TextToSpeech._CAL_L0_TEMPLATES, "CAL-L0 templates")

    def test_reasonable_size_preserved(self):
        # Guards against an accidental near-empty override during a future edit.
        from core.tts import TextToSpeech
        assert len(TextToSpeech._CAL_L0_TEMPLATES) > 100


class TestPersonaPoolsAreGerman:
    def test_no_banned_english_phrases_in_ack_cache(self):
        from core import persona
        phrases = [p for p, _style in persona.pool_tagged("ack_cache")]
        _assert_no_banned_phrases(phrases, "persona ack_cache pool")

    def test_no_banned_english_phrases_across_all_pools(self):
        from core import persona
        # _POOLS is intentionally "private" but this is exactly the kind
        # of regression guard that needs to see the real, current pool
        # content after the DE-DE override has been applied.
        for category, items in persona._POOLS.items():
            phrases = [p for p, *_ in items] if items and isinstance(items[0], tuple) else list(items)
            _assert_no_banned_phrases(phrases, f"persona pool '{category}'")


class TestResponseLibraryIsGerman:
    def test_no_banned_english_phrases(self):
        from core.responses import get_response_library
        lib = get_response_library()
        for category, phrases in lib.responses.items():
            _assert_no_banned_phrases(phrases, f"ResponseLibrary category '{category}'")
