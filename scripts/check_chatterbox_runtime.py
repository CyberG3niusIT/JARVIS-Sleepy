#!/usr/bin/env python3
"""Validate the canonical JARVIS Chatterbox runtime before JARVIS starts.

Stdlib only. The check verifies the local voice anchor and the server's
/health + /config contract against systemd/chatterbox.env.

Default behavior is strict: a configured Chatterbox primary must be healthy and
must expose the canonical voice parameters. Set JARVIS_ALLOW_DEGRADED_TTS=1
explicitly to allow startup with Piper fallback while the primary is unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / "systemd" / "chatterbox.env"
FLOAT_KEYS = (
    "tempo",
    "exaggeration",
    "cfg_weight",
    "temperature",
    "repetition_penalty",
    "min_p",
    "top_p",
)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Ungültige Zeile in {path}: {raw!r}")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def http_json(url: str, timeout: float = 2.0) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def expected_contract(env: dict[str, str]) -> dict:
    return {
        "language": env["CHATTERBOX_LANGUAGE"],
        "tempo": float(env["CHATTERBOX_TEMPO"]),
        "audio_prompt_path": env["CHATTERBOX_AUDIO_PROMPT_PATH"],
        "audio_prompt_sha256": env["CHATTERBOX_AUDIO_PROMPT_SHA256"],
        "exaggeration": float(env["CHATTERBOX_EXAGGERATION"]),
        "cfg_weight": float(env["CHATTERBOX_CFG_WEIGHT"]),
        "temperature": float(env["CHATTERBOX_TEMPERATURE"]),
        "repetition_penalty": float(env["CHATTERBOX_REPETITION_PENALTY"]),
        "min_p": float(env["CHATTERBOX_MIN_P"]),
        "top_p": float(env["CHATTERBOX_TOP_P"]),
    }


def compare_contract(actual: dict, expected: dict) -> list[str]:
    errors: list[str] = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if key in FLOAT_KEYS:
            try:
                if abs(float(actual_value) - float(expected_value)) > 1e-9:
                    errors.append(f"{key}: erwartet {expected_value}, ist {actual_value}")
            except (TypeError, ValueError):
                errors.append(f"{key}: erwartet {expected_value}, ist {actual_value!r}")
        elif actual_value != expected_value:
            errors.append(f"{key}: erwartet {expected_value!r}, ist {actual_value!r}")
    return errors


def validate_once(env_file: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if not env_file.is_file():
        return False, [f"Runtime-Konfiguration fehlt: {env_file}"]

    try:
        env = parse_env_file(env_file)
        expected = expected_contract(env)
    except Exception as exc:
        return False, [f"Runtime-Konfiguration ungültig: {exc}"]

    anchor = Path(expected["audio_prompt_path"])
    if not anchor.is_file():
        errors.append(f"Voice-Anker fehlt: {anchor}")
    else:
        actual_sha = file_sha256(anchor)
        if actual_sha != expected["audio_prompt_sha256"]:
            errors.append(
                "Voice-Anker SHA256 stimmt nicht: "
                f"erwartet {expected['audio_prompt_sha256']}, ist {actual_sha}"
            )

    port = env.get("CHATTERBOX_PORT", "8765")
    base = f"http://127.0.0.1:{port}"

    try:
        health = http_json(f"{base}/health")
        if health.get("status") != "ok":
            errors.append(f"/health meldet {health!r}")
    except Exception as exc:
        errors.append(f"{base}/health nicht erreichbar: {exc}")
        return False, errors

    try:
        actual = http_json(f"{base}/config")
        errors.extend(compare_contract(actual, expected))
    except Exception as exc:
        errors.append(f"{base}/config nicht erreichbar/ungültig: {exc}")

    return not errors, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument(
        "--wait",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="Bis zu SECONDS auf einen gültigen Chatterbox-Runtimezustand warten.",
    )
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument(
        "--verbose-diagnostics",
        action="store_true",
        help="Zeigt lokale Pfade und Detailfehler für manuelle Diagnose an.",
    )
    args = parser.parse_args(argv)

    deadline = time.monotonic() + max(0.0, args.wait)
    last_errors: list[str] = []

    while True:
        ok, last_errors = validate_once(args.env_file)
        if ok:
            print("OK: Chatterbox Runtime entspricht der kanonischen JARVIS Voice-Baseline.")
            return 0
        if time.monotonic() >= deadline:
            break
        time.sleep(max(0.1, args.interval))

    if os.environ.get("JARVIS_ALLOW_DEGRADED_TTS") == "1":
        print("WARN: Chatterbox Runtime ist nicht kanonisch/erreichbar; expliziter Degraded Mode erlaubt.", file=sys.stderr)
        for error in last_errors:
            print(f"  - {error}", file=sys.stderr)
        return 0

    print("FEHLER: Chatterbox Runtime ist nicht startbereit.", file=sys.stderr)
    if args.verbose_diagnostics:
        for error in last_errors:
            print(f"  - {error}", file=sys.stderr)
    print(
        "Für einen bewusst gewünschten Piper-Degraded-Start: "
        "JARVIS_ALLOW_DEGRADED_TTS=1 setzen.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
