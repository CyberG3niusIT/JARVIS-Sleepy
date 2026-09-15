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
        # so it must fall through to the decimal case, not be silently
        # dropped or mis-split by the thousands grouping.
        assert "drei Komma fünf" in _norm("Version 3.5 ist neu.")


class TestUnitBearingNumbersWithGrouping:
    """A number with a unit (currency/percent/file-size/temperature) must
    be captured as ONE token even when German-thousands-grouped — a
    narrower per-unit regex used to only match the last 3-digit group,
    e.g. "1.234,56 €" produced the garbage "1.zweihundertvierunddreißig
    Komma fünf sechs Euro" (stray literal "1." left over)."""

    def test_grouped_euro_symbol_suffix(self):
        assert _norm("Das kostet 10.000 €.") == "Das kostet zehntausend Euro."

    def test_grouped_percent(self):
        assert _norm("Das sind 10.000 % mehr.") == "Das sind zehntausend Prozent mehr."

    def test_grouped_file_size(self):
        assert _norm("Die Datei ist 10.000 MB groß.") == "Die Datei ist zehntausend Megabyte groß."

    def test_grouped_with_decimal_tail_euro(self):
        result = _norm("Der Umsatz betrug 1.234,56 €.")
        assert "1." not in result  # no stray leftover fragment
        assert result == "Der Umsatz betrug eintausendzweihundertvierunddreißig Komma fünf sechs Euro."

    def test_grouped_with_decimal_tail_file_size(self):
        result = _norm("Datei: 1.234,5 MB.")
        assert "1." not in result
        assert "eintausendzweihundertvierunddreißig Komma fünf Megabyte" in result

    def test_multi_group_million_euro(self):
        assert _norm("Der Jackpot: 1.000.000 €.") == "Der Jackpot: eine Million Euro."

    def test_plain_decimal_percent_unaffected(self):
        assert _norm("3,5 % Zinsen.") == "drei Komma fünf Prozent Zinsen."

    def test_negative_temperature(self):
        assert _norm("Es sind -3,5°C draußen.") == "Es sind minus drei Komma fünf Grad Celsius draußen."

    def test_ipv4_unaffected_by_grouping_change(self):
        # IPv4 is normalized by its own earlier pass — must still win
        # over the general grouped-number token.
        result = _norm("Die IP ist 192.168.1.1.")
        assert result == "Die IP ist eins neun zwei Punkt eins sechs acht Punkt eins Punkt eins."

    def test_date_unaffected_by_grouping_change(self):
        result = _norm("Der Termin ist am 24.09.2026.")
        assert "vierundzwanzigste September zweitausendsechsundzwanzig" in result


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
