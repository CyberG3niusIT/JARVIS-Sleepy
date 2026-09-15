"""
Deutscher TTS-Normalizer fuer JARVIS.
Bereitet Text vollstaendig fuer deutsche Sprachausgabe vor.
"""

import re
from typing import Callable, Dict


class GermanTTSNormalizer:

    ONES = (
        "null", "eins", "zwei", "drei", "vier",
        "fünf", "sechs", "sieben", "acht", "neun"
    )

    TEENS = {
        10: "zehn",
        11: "elf",
        12: "zwölf",
        13: "dreizehn",
        14: "vierzehn",
        15: "fünfzehn",
        16: "sechzehn",
        17: "siebzehn",
        18: "achtzehn",
        19: "neunzehn",
    }

    TENS = {
        20: "zwanzig",
        30: "dreißig",
        40: "vierzig",
        50: "fünfzig",
        60: "sechzig",
        70: "siebzig",
        80: "achtzig",
        90: "neunzig",
    }

    MONTHS = {
        "01": "Januar",
        "02": "Februar",
        "03": "März",
        "04": "April",
        "05": "Mai",
        "06": "Juni",
        "07": "Juli",
        "08": "August",
        "09": "September",
        "10": "Oktober",
        "11": "November",
        "12": "Dezember",
    }

    DAY_ORDINALS = {
        1: "erste",
        2: "zweite",
        3: "dritte",
        4: "vierte",
        5: "fünfte",
        6: "sechste",
        7: "siebte",
        8: "achte",
        9: "neunte",
        10: "zehnte",
        11: "elfte",
        12: "zwölfte",
        13: "dreizehnte",
        14: "vierzehnte",
        15: "fünfzehnte",
        16: "sechzehnte",
        17: "siebzehnte",
        18: "achtzehnte",
        19: "neunzehnte",
        20: "zwanzigste",
        21: "einundzwanzigste",
        22: "zweiundzwanzigste",
        23: "dreiundzwanzigste",
        24: "vierundzwanzigste",
        25: "fünfundzwanzigste",
        26: "sechsundzwanzigste",
        27: "siebenundzwanzigste",
        28: "achtundzwanzigste",
        29: "neunundzwanzigste",
        30: "dreißigste",
        31: "einunddreißigste",
    }

    def __init__(self):
        self.normalizations: Dict[str, Callable] = {
            "markdown": self.normalize_markdown,
            "dates": self.normalize_dates,
            "times": self.normalize_times,
            "ipv4": self.normalize_ipv4,
            "temperatures": self.normalize_temperatures,
            "file_sizes": self.normalize_file_sizes,
            "currency": self.normalize_currency,
            "percent": self.normalize_percent,
            "urls": self.normalize_urls,
            # Must run before "decimals": German groups thousands with "."
            # (10.000 = zehntausend) while English-style decimals use ".".
            # Without this, normalize_decimals treats the grouping dot as a
            # decimal point and reads "10.000" as "zehn Komma null null null".
            "thousands": self.normalize_thousands,
            "decimals": self.normalize_decimals,
            "technical": self.normalize_technical_terms,
            "numbers": self.normalize_numbers,
        }

    def normalize(self, text: str) -> str:
        if not text:
            return text

        result = text

        for func in self.normalizations.values():
            result = func(result)

        result = re.sub(r"\s+", " ", result)
        return result.strip()

    # ---------------------------------------------------------
    # Zahlen
    # ---------------------------------------------------------

    def number_to_words(self, n: int) -> str:
        if n < 0:
            return "minus " + self.number_to_words(-n)

        if n < 10:
            return self.ONES[n]

        if n < 20:
            return self.TEENS[n]

        if n < 100:
            tens = (n // 10) * 10
            ones = n % 10

            if ones == 0:
                return self.TENS[tens]

            one = "ein" if ones == 1 else self.ONES[ones]
            return one + "und" + self.TENS[tens]

        if n < 1000:
            hundreds = n // 100
            rest = n % 100

            prefix = (
                "einhundert"
                if hundreds == 1
                else self.number_to_words(hundreds) + "hundert"
            )

            return prefix + (
                self.number_to_words(rest)
                if rest
                else ""
            )

        if n < 1_000_000:
            thousands = n // 1000
            rest = n % 1000

            prefix = (
                "eintausend"
                if thousands == 1
                else self.number_to_words(thousands) + "tausend"
            )

            return prefix + (
                self.number_to_words(rest)
                if rest
                else ""
            )

        if n < 1_000_000_000:
            millions = n // 1_000_000
            rest = n % 1_000_000

            if millions == 1:
                prefix = "eine Million"
            else:
                prefix = self.number_to_words(millions) + " Millionen"

            if rest:
                return prefix + " " + self.number_to_words(rest)

            return prefix

        return str(n)

    def decimal_to_words(self, raw: str) -> str:
        raw = raw.replace(",", ".")

        if "." not in raw:
            return self.number_to_words(int(raw))

        whole, frac = raw.split(".", 1)

        whole_words = self.number_to_words(int(whole))
        frac_words = " ".join(
            self.ONES[int(d)]
            for d in frac
        )

        return f"{whole_words} Komma {frac_words}"

    # ---------------------------------------------------------
    # Formatierungen
    # ---------------------------------------------------------

    def normalize_markdown(self, text: str) -> str:
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        text = re.sub(r"~~(.+?)~~", r"\1", text)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        return text

    def normalize_dates(self, text: str) -> str:

        def numeric_date(match):
            day = int(match.group(1))
            month = match.group(2)
            year = int(match.group(3))

            if day not in self.DAY_ORDINALS:
                return match.group(0)

            month_name = self.MONTHS.get(month)
            if not month_name:
                return match.group(0)

            return (
                f"{self.DAY_ORDINALS[day]} "
                f"{month_name} "
                f"{self.number_to_words(year)}"
            )

        text = re.sub(
            r"\b(\d{1,2})\.(\d{2})\.(\d{4})\b",
            numeric_date,
            text,
        )

        months = "|".join(self.MONTHS.values())

        def written_date(match):
            day = int(match.group(1))
            month = match.group(2)
            year = match.group(3)

            if day not in self.DAY_ORDINALS:
                return match.group(0)

            result = f"{self.DAY_ORDINALS[day]} {month}"

            if year:
                result += " " + self.number_to_words(int(year))

            return result

        text = re.sub(
            rf"\b(\d{{1,2}})\.\s+({months})(?:\s+(\d{{4}}))?\b",
            written_date,
            text,
            flags=re.IGNORECASE,
        )

        return text

    def normalize_times(self, text: str) -> str:

        def repl(match):
            hour = int(match.group(1))
            minute = int(match.group(2))

            result = self.number_to_words(hour) + " Uhr"

            if minute:
                result += " " + self.number_to_words(minute)

            return result

        # Swallow an already-present trailing "Uhr" so "14:30 Uhr" doesn't
        # become "vierzehn Uhr dreißig Uhr" — the replacement already adds
        # its own "Uhr".
        return re.sub(
            r"\b([01]?\d|2[0-3]):([0-5]\d)\b(?:\s*Uhr\b)?",
            repl,
            text,
        )

    def normalize_ipv4(self, text: str) -> str:

        def repl(match):
            groups = match.group(0).split(".")
            spoken_groups = []

            for group in groups:
                spoken_groups.append(
                    " ".join(
                        self.ONES[int(d)]
                        for d in group
                    )
                )

            return " Punkt ".join(spoken_groups)

        return re.sub(
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
            repl,
            text,
        )

    def normalize_temperatures(self, text: str) -> str:

        def repl(match):
            value = self.decimal_to_words(match.group(1))
            unit = match.group(2).upper()

            name = (
                "Celsius"
                if unit == "C"
                else "Fahrenheit"
            )

            return f"{value} Grad {name}"

        return re.sub(
            r"(-?\d+(?:[.,]\d+)?)\s*°?\s*([CFcf])\b",
            repl,
            text,
        )

    def normalize_file_sizes(self, text: str) -> str:
        units = {
            "KB": "Kilobyte",
            "MB": "Megabyte",
            "GB": "Gigabyte",
            "TB": "Terabyte",
            "PB": "Petabyte",
        }

        def repl(match):
            value = self.decimal_to_words(match.group(1))
            unit = units[match.group(2).upper()]
            return f"{value} {unit}"

        return re.sub(
            r"\b(\d+(?:[.,]\d+)?)\s*(KB|MB|GB|TB|PB)\b",
            repl,
            text,
            flags=re.IGNORECASE,
        )

    def normalize_currency(self, text: str) -> str:

        def euro_prefix(match):
            return (
                self.decimal_to_words(match.group(1))
                + " Euro"
            )

        def euro_suffix(match):
            return (
                self.decimal_to_words(match.group(1))
                + " Euro"
            )

        def dollar(match):
            return (
                self.decimal_to_words(match.group(1))
                + " Dollar"
            )

        text = re.sub(
            r"€\s*(\d+(?:[.,]\d+)?)",
            euro_prefix,
            text,
        )

        text = re.sub(
            r"(\d+(?:[.,]\d+)?)\s*€",
            euro_suffix,
            text,
        )

        text = re.sub(
            r"\$\s*(\d+(?:[.,]\d+)?)",
            dollar,
            text,
        )

        return text

    def normalize_percent(self, text: str) -> str:

        def repl(match):
            return (
                self.decimal_to_words(match.group(1))
                + " Prozent"
            )

        return re.sub(
            r"\b(\d+(?:[.,]\d+)?)\s*%",
            repl,
            text,
        )

    def normalize_urls(self, text: str) -> str:
        return re.sub(
            r"https?://(?:www\.)?([a-zA-Z0-9\-]+(?:\.[a-zA-Z0-9\-]+)+)",
            lambda m: m.group(1).replace(".", " Punkt "),
            text,
        )

    def normalize_thousands(self, text: str) -> str:
        """German thousands grouping: 10.000 -> zehntausend, 1.234.567 -> ...

        German uses "." to group thousands and "," as the decimal separator
        (the reverse of English). Matches only proper 3-digit groupings so
        it never eats a genuine decimal like "3.5" (which has fewer than
        3 digits after the dot).
        """

        def repl(match):
            return self.number_to_words(int(match.group(0).replace(".", "")))

        return re.sub(
            r"(?<![\w.,])\d{1,3}(?:\.\d{3})+(?![\d,])",
            repl,
            text,
        )

    def normalize_decimals(self, text: str) -> str:

        def repl(match):
            return self.decimal_to_words(match.group(0))

        return re.sub(
            r"(?<![\w.])\-?\d+[.,]\d+(?![\w.])",
            repl,
            text,
        )

    def normalize_technical_terms(self, text: str) -> str:
        replacements = {
            r"\bCPU\b": "C P U",
            r"\bGPU\b": "G P U",
            r"\bAPI\b": "A P I",
            r"\bUSB\b": "U S B",
            r"\bSSH\b": "S S H",
            r"\bTCP\b": "T C P",
            r"\bUDP\b": "U D P",
            r"\bHTTP\b": "H T T P",
            r"\bHTTPS\b": "H T T P S",
            r"\bDNS\b": "D N S",
            r"\bVPN\b": "V P N",
            r"\bURL\b": "U R L",
            r"\bHTML\b": "H T M L",
            r"\bCSS\b": "C S S",
            r"\bSQL\b": "S Q L",
            r"\bXML\b": "X M L",
            r"\bPDF\b": "P D F",
        }

        for pattern, replacement in replacements.items():
            text = re.sub(
                pattern,
                replacement,
                text,
                flags=re.IGNORECASE,
            )

        return text

    def normalize_numbers(self, text: str) -> str:

        def repl(match):
            return self.number_to_words(
                int(match.group(0))
            )

        return re.sub(
            r"(?<![\w.,])\-?\d{1,9}(?![\w.,])",
            repl,
            text,
        )

    def register_normalization(
        self,
        name: str,
        func: Callable[[str], str],
    ) -> None:
        self.normalizations[name] = func

    def unregister_normalization(self, name: str) -> None:
        self.normalizations.pop(name, None)


_normalizer_instance = None


def get_normalizer() -> GermanTTSNormalizer:
    global _normalizer_instance

    if _normalizer_instance is None:
        _normalizer_instance = GermanTTSNormalizer()

    return _normalizer_instance
