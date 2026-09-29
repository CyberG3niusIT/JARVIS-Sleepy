"""Repository gate: WPF is retired. The only desktop client is WinUI 3 (WindowsApp/WinUI3).

Static architecture test (no Windows SDK needed). Fails if a WPF build, runtime or test path
reappears. Decision record: docs/DESKTOP_ARCHITECTURE.md.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Matched case-insensitively. Built from parts so this file cannot match itself.
FORBIDDEN = tuple(p.lower() for p in (
    "Use" + "WPF",
    "System" + ".Windows",
    "Presentation" + "Framework",
    "Presentation" + "Core",
    "Windows" + "Base",
    "Microsoft.WindowsDesktop.App" + ".WPF",
    "Microsoft.NET.Sdk" + ".WindowsDesktop",
    "Jarvis.ControlHub" + ".csproj",
))

# No exemptions: every file in scope is a build, runtime or test path or active documentation of one.
BUILD_FILES = {".csproj", ".sln", ".props", ".targets", ".vbproj", ".fsproj"}
DESKTOP_TEST_FILES = BUILD_FILES | {".cs", ".xaml", ".resx", ".json", ".config", ".manifest", ".ps1"}
SKIP_DIRS = {".git", "bin", "obj", "node_modules", "__pycache__", ".venv", "venv"}


def _files(base: Path):
    for path in base.rglob("*"):
        if path.is_file() and not SKIP_DIRS.intersection(path.relative_to(ROOT).parts):
            yield path


def _projects():
    return sorted(p for p in _files(ROOT) if p.suffix.lower() in BUILD_FILES)


def _scanned():
    seen = set(_files(ROOT / "WindowsApp"))
    seen.update(p for p in _files(ROOT / "tests") if p.suffix.lower() in DESKTOP_TEST_FILES)
    seen.update(_projects())
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
        for number, line in enumerate(text.lower().splitlines(), 1):
            offenders.extend(f"{path.relative_to(ROOT)}:{number}: {pattern}" for pattern in FORBIDDEN if pattern in line)
    assert not offenders, "WPF is retired; WinUI 3 is the only desktop client:\n" + "\n".join(offenders)


def test_desktop_app_project_is_winui_only():
    projects = sorted(p.relative_to(ROOT).as_posix() for p in _files(ROOT / "WindowsApp") if p.suffix.lower() in BUILD_FILES)
    assert projects == ["WindowsApp/WinUI3/Jarvis.ControlHub.WinUI.csproj"], projects
    project = (ROOT / "WindowsApp/WinUI3/Jarvis.ControlHub.WinUI.csproj").read_text(encoding="utf-8")
    assert "<UseWinUI>true</UseWinUI>" in project
    assert "Microsoft.WindowsAppSDK" in project


def test_every_project_reference_exists():
    missing = []
    for project in _projects():
        for include in re.findall(r'<ProjectReference\s+Include="([^"]+)"', project.read_text(encoding="utf-8"), re.IGNORECASE):
            target = (project.parent / include.replace("\\", "/")).resolve()
            if not target.is_file():
                missing.append(f"{project.relative_to(ROOT)} -> {include}")
    assert not missing, "ProjectReference to a missing project:\n" + "\n".join(missing)
