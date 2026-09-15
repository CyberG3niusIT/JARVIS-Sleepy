"""Unit tests for the German TTS normalizer and speech chunker.

Covers the bugs found during the September 2026 TTS pipeline audit:
- German thousands grouping vs. decimal comma (10.000 vs. 3,5)
- Duplicate "Uhr" when the source text already has a trailing "Uhr"
- German abbreviations no longer causing false sentence-boundary splits
- people_manager wiring to the normalizer speech.py actually uses
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.tts_normalizer_de import GermanTTSNormalizer
from core.speech_chunker import SpeechChunker


def _norm(text: str) -> str:
    return GermanTTSNormalizer().normalize(text)


class TestThousandsGrouping:
    def test_simple_thousands(self):
        assert _norm("Das kostet 10.000 Euro.") == "Das kostet zehntausend Euro."

    def test_large_grouped_number(self):
        result = _norm("Es waren 1.234.567 Besucher.")
        assert "million" in result.lower() or "Million" in result

    def test_decimal_comma_still_works(self):
        # German decimals use a comma, not a dot — must not be mistaken
        # for thousands grouping.
        assert "Komma" in _norm("Der Wert ist 3,5 Prozent.")

    def test_short_english_style_decimal_not_grouped(self):
        # "3.5" only has one digit after the dot — not a 3-digit group,
        # so it must fall through to normalize_decimals, not be silently
        # dropped or mis-split by the thousands regex.
        assert "drei Komma fünf" in _norm("Version 3.5 ist neu.")


class TestTimeNormalization:
    def test_no_duplicate_uhr(self):
        result = _norm("Es ist 14:30 Uhr.")
        assert result.count("Uhr") == 1
        assert result == "Es ist vierzehn Uhr dreißig."

    def test_time_without_trailing_uhr_unaffected(self):
        result = _norm("Der Termin ist um 9:05.")
        assert result == "Der Termin ist um neun Uhr fünf."


class TestGermanAbbreviationsInChunker:
    """SpeechChunker must not split mid-sentence on German abbreviations —
    doing so chops prosody exactly where clean speech matters most."""

    @staticmethod
    def _feed_all(text: str):
        chunker = SpeechChunker()
        chunks = []
        for word in text.split(" "):
            chunk = chunker.feed(word + " ")
            if chunk:
                chunks.append(chunk)
        tail = chunker.flush()
        if tail:
            chunks.append(tail)
        return chunks

    def test_zb_does_not_split(self):
        chunks = self._feed_all("Nimm z.B. den Zug. Das ist schneller.")
        assert len(chunks) == 2
        assert chunks[0].startswith("Nimm z.B. den Zug.")

    def test_bzw_does_not_split(self):
        chunks = self._feed_all("Das ist neu, bzw. überarbeitet. Gut so.")
        assert len(chunks) == 2

    def test_usw_does_not_split(self):
        chunks = self._feed_all("Äpfel, Birnen usw. sind Obst. Ende.")
        assert len(chunks) == 2

    def test_real_sentence_boundary_still_splits(self):
        chunks = self._feed_all("Hallo Welt. Wie geht es dir?")
        assert len(chunks) == 2


class TestPeopleManagerNormalizerWiring:
    """core/people_manager.py must register pronunciation overrides with
    the normalizer core/tts.py actually speaks through (tts_normalizer_de),
    not the unused English tts_normalizer — otherwise overrides silently
    never apply."""

    def test_registers_with_german_normalizer(self, monkeypatch):
        import core.people_manager as pm_module

        captured = {}

        class FakeNormalizer:
            def register_normalization(self, name, func):
                captured["name"] = name
                captured["func"] = func

        monkeypatch.setattr(
            "core.tts_normalizer_de.get_normalizer", lambda: FakeNormalizer()
        )

        # Build a minimal PeopleManager-like object bound to the real method.
        class Stub:
            logger = type("L", (), {"warning": lambda *a, **k: None})()
            _name_substitution = lambda self, text: text

        pm_module.PeopleManager._register_tts_normalizer(Stub())

        assert captured.get("name") == "people_names"
