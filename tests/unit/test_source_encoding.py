"""Guards against source files saved as double-encoded UTF-8 (UTF-8 bytes re-read as cp1252)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Lead byte of a UTF-8 sequence read as cp1252 ("A-tilde"/"A-circumflex" + continuation, or "a-circumflex euro/dagger").
MOJIBAKE = re.compile("%s[%s-%s]|%s[%s-%s]|%s%s|%s%s" % (
    chr(0xC3), chr(0x80), chr(0xBF), chr(0xC2), chr(0x80), chr(0xBF), chr(0xE2), chr(0x20AC), chr(0xE2), chr(0x2020)))
SCANNED = ("jarvis_web.py", "core", "skills", "scripts", "web", "tests")
SUFFIXES = {".py", ".js", ".html", ".css", ".ps1", ".sh"}


def _sources():
    for entry in SCANNED:
        path = ROOT / entry
        candidates = [path] if path.is_file() else path.rglob("*")
        for file in candidates:
            if file.suffix in SUFFIXES and "__pycache__" not in file.parts and file.is_file():
                yield file


def test_sources_are_not_double_encoded():
    offenders = []
    for file in _sources():
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            offenders.append(f"{file.relative_to(ROOT)}: not UTF-8")
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if MOJIBAKE.search(line):
                offenders.append(f"{file.relative_to(ROOT)}:{number}: {line.strip()[:80]}")
    assert not offenders, "double-encoded UTF-8:\n" + "\n".join(offenders[:20])
