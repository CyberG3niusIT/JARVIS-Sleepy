"""Isolation tests for the core.capabilities package.

The package must stay passive: no side effects on import, no coupling to
runtime modules, no global registry instances and no consumers in production
code. The static checks below are hygiene checks on the source text, not a
security proof.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = REPO_ROOT / "core" / "capabilities"

PACKAGE_FILES = (
    "__init__.py",
    "vocabulary.py",
    "contract.py",
    "manifest.py",
    "registry.py",
)
SUBMODULES = tuple(
    f"core.capabilities.{name[:-3]}" for name in PACKAGE_FILES if name != "__init__.py"
)

FORBIDDEN_LOADED_MODULES = (
    "core.privacy_gate",
    "core.tool_registry",
    "core.governance",
    "core.event_logger",
    "core.llm_router",
    "core.conversation_router",
    "core.skill_manager",
    "core.mcp_client",
    "sqlite3",
    "socket",
    "requests",
    "httpx",
    "urllib.request",
)

FORBIDDEN_IMPORT_PARTS = frozenset({
    "privacy_gate", "governance", "event_logger", "tool_registry",
    "sqlite3", "socket", "requests", "httpx", "urllib", "subprocess",
})

GLOBAL_INSTANCE_NAMES = frozenset({
    "CapabilityRegistry", "ProviderManifest", "CapabilitySpec",
    "ProviderDescriptor",
})

SKIPPED_DIRS = frozenset({
    "__pycache__", ".venv", "venv", "node_modules", ".git",
})


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _package_trees():
    return [(name, _parse(PACKAGE_DIR / name)) for name in PACKAGE_FILES]


# ---------------------------------------------------------------------------
# Import has no side effects
# ---------------------------------------------------------------------------

def test_import_in_fresh_process_loads_no_runtime_or_io_modules():
    code = (
        "import importlib, json, sys\n"
        "importlib.import_module('core.capabilities')\n"
        f"for name in {list(SUBMODULES)!r}:\n"
        "    importlib.import_module(name)\n"
        "print(json.dumps(sorted(sys.modules)))\n"
    )
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-S", "-c", code],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    loaded = set(json.loads(result.stdout.strip().splitlines()[-1]))

    # The probe only means something if the package really was imported.
    assert "core.capabilities" in loaded
    for name in SUBMODULES:
        assert name in loaded

    leaked = [name for name in FORBIDDEN_LOADED_MODULES if name in loaded]
    assert leaked == []


# ---------------------------------------------------------------------------
# Source hygiene (AST based, not a security proof)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", PACKAGE_FILES)
def test_package_source_has_no_forbidden_imports_or_io_access(filename):
    tree = _parse(PACKAGE_DIR / filename)
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if FORBIDDEN_IMPORT_PARTS.intersection(alias.name.split(".")):
                    problems.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if FORBIDDEN_IMPORT_PARTS.intersection(module.split(".")):
                problems.append(f"line {node.lineno}: from {module} import ...")
            for alias in node.names:
                if alias.name in FORBIDDEN_IMPORT_PARTS | {"environ"}:
                    problems.append(
                        f"line {node.lineno}: from {module} import {alias.name}")
        elif isinstance(node, ast.Attribute) and node.attr == "environ":
            problems.append(f"line {node.lineno}: environ access")
        elif isinstance(node, ast.Name) and node.id in {"open", "environ"}:
            problems.append(f"line {node.lineno}: use of {node.id}")
    assert problems == []


# ---------------------------------------------------------------------------
# No consumers outside the package
# ---------------------------------------------------------------------------

def _imports_capabilities(tree: ast.Module, path: Path) -> list[int]:
    hits: list[int] = []
    in_core_top = path.parent == REPO_ROOT / "core"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "core.capabilities" or alias.name.startswith(
                        "core.capabilities."):
                    hits.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0:
                if module == "core.capabilities" or module.startswith(
                        "core.capabilities."):
                    hits.append(node.lineno)
                elif module == "core" and any(
                        a.name == "capabilities" for a in node.names):
                    hits.append(node.lineno)
            elif in_core_top and node.level == 1:
                if module == "capabilities" or module.startswith("capabilities."):
                    hits.append(node.lineno)
                elif not module and any(a.name == "capabilities" for a in node.names):
                    hits.append(node.lineno)
    return hits


def _production_python_files():
    files = sorted(REPO_ROOT.glob("*.py"))
    for top in ("core", "skills", "scripts"):
        base = REPO_ROOT / top
        if not base.is_dir():
            continue
        for current, dirs, names in os.walk(base):
            dirs[:] = [d for d in dirs if d not in SKIPPED_DIRS]
            current_path = Path(current)
            if current_path == PACKAGE_DIR or PACKAGE_DIR in current_path.parents:
                continue
            files.extend(current_path / n for n in sorted(names) if n.endswith(".py"))
    return files


def test_no_production_module_imports_capabilities():
    offenders: list[str] = []
    scanned = 0
    for path in _production_python_files():
        try:
            tree = _parse(path)
        except (SyntaxError, UnicodeDecodeError, ValueError):
            # Unparsable file: fall back to a plain text check.
            text = path.read_text(encoding="utf-8", errors="replace")
            if "core.capabilities" in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)} (text)")
            continue
        scanned += 1
        for lineno in _imports_capabilities(tree, path):
            offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
    assert scanned > 0
    assert offenders == []


# ---------------------------------------------------------------------------
# No module-level instances
# ---------------------------------------------------------------------------

def _called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _load_time_calls(node: ast.AST):
    """Yield calls executed at import time (skips function and lambda bodies)."""
    stack = [node]
    while stack:
        current = stack.pop()
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(child, ast.Call):
                yield child
            stack.append(child)


@pytest.mark.parametrize("filename", PACKAGE_FILES)
def test_no_module_level_registry_or_contract_instances(filename):
    tree = _parse(PACKAGE_DIR / filename)
    offenders = [
        f"line {call.lineno}: {_called_name(call)}(...)"
        for call in _load_time_calls(tree)
        if _called_name(call) in GLOBAL_INSTANCE_NAMES
    ]
    assert offenders == []


# ---------------------------------------------------------------------------
# Package layout and auto-discovery path
# ---------------------------------------------------------------------------

def test_package_contains_exactly_the_expected_files():
    files = {
        entry.name
        for entry in PACKAGE_DIR.iterdir()
        if entry.is_file() and entry.suffix != ".pyc"
    }
    assert files == set(PACKAGE_FILES)
    subdirs = {entry.name for entry in PACKAGE_DIR.iterdir() if entry.is_dir()}
    assert subdirs <= {"__pycache__"}


def test_tool_auto_discovery_path_does_not_reference_capabilities():
    tools_dir = REPO_ROOT / "core" / "tools"
    if not tools_dir.is_dir():
        return
    offenders: list[str] = []
    for current, dirs, names in os.walk(tools_dir):
        dirs[:] = [d for d in dirs if d not in SKIPPED_DIRS]
        for name in names:
            path = Path(current) / name
            text = path.read_text(encoding="utf-8", errors="replace")
            if "core.capabilities" in text or "from core import capabilities" in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []
