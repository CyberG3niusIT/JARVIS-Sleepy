"""Repository gate: WPF is retired. The only desktop client is WinUI 3 (WindowsApp/WinUI3).

Fails if a WPF build, runtime or test path reappears. See docs/DESKTOP_ARCHITECTURE.md.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Built from parts so this gate file never matches itself.
FORBIDDEN = (
    "Use" + "WPF",
    "System" + ".Windows",
    "Presentation" + "Framework",
    "Presentation" + "Core",
    "Windows" + "Base",
    "Microsoft.WindowsDesktop.App" + ".WPF",
    "Microsoft.NET.Sdk" + ".WindowsDesktop",
    "Jarvis.ControlHub" + ".csproj",
)

# Only Markdown that declares itself historical may mention these; never code, project or test files.
HISTORICAL_MARKER = "<!-- " + "historical-document: retired WPF -->"

BUILD_FILES = {".csproj", ".sln", ".props", ".targets", ".vbproj", ".fsproj"}
DESKTOP_TEST_FILES = BUILD_FILES | {".cs", ".xaml", ".resx", ".json", ".config", ".manifest", ".ps1"}
SKIP_DIRS = {".git", "bin", "obj", "node_modules", "__pycache__", ".venv", "venv"}


def _files(base: Path):
    for path in base.rglob("*"):
        if path.is_file() and not SKIP_DIRS.intersection(path.relative_to(ROOT).parts):
            yield path


def _scanned():
    seen = set()
    for path in _files(ROOT / "WindowsApp"):
        seen.add(path)
    for path in _files(ROOT / "tests"):
        if path.suffix.lower() in DESKTOP_TEST_FILES:
            seen.add(path)
    for path in _files(ROOT):
        if path.suffix.lower() in BUILD_FILES:
            seen.add(path)
    return sorted(seen)


def _text(path: Path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None  # binary asset (image, font)


def test_no_wpf_in_desktop_build_runtime_or_tests():
    offenders = []
    for path in _scanned():
        text = _text(path)
        if text is None:
            continue
        if path.suffix.lower() == ".md" and HISTORICAL_MARKER in text:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for pattern in FORBIDDEN:
                if pattern in line:
                    offenders.append(f"{path.relative_to(ROOT)}:{number}: {pattern}")
    assert not offenders, "WPF is retired; WinUI 3 is the only desktop client:\n" + "\n".join(offenders)


def test_desktop_app_project_is_winui_only():
    projects = sorted(p.relative_to(ROOT).as_posix() for p in _files(ROOT / "WindowsApp") if p.suffix.lower() in BUILD_FILES)
    assert projects == ["WindowsApp/WinUI3/Jarvis.ControlHub.WinUI.csproj"], projects
    project = (ROOT / "WindowsApp/WinUI3/Jarvis.ControlHub.WinUI.csproj").read_text(encoding="utf-8")
    assert "<UseWinUI>true</UseWinUI>" in project
    assert "Microsoft.WindowsAppSDK" in project
