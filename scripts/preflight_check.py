#!/usr/bin/env python3
"""JARVIS Preflight Check — reproducible pre-start validation.

Checks the things that actually determine whether jarvis_continuous.py
will come up cleanly on Sleepy: LLM/Chatterbox servers, STT model,
audio devices, data paths, disk space, and required executables.

Short, German output, one line per check. Not a diagnostics framework —
just "can I start, and if not, why."

Usage:
    python3 scripts/preflight_check.py

Exit code 0 if nothing CRITICAL failed (WARN-level issues are printed
but don't fail the run — e.g. Chatterbox down is degraded-but-usable
since Piper is a real fallback), 1 otherwise.
"""

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK = "\033[32m✅\033[0m"
WARN = "\033[33m⚠️ \033[0m"
FAIL = "\033[31m❌\033[0m"

_results = []  # (level, name, detail) — level in {"ok", "warn", "fail"}


def check(name):
    """Decorator: run `fn()`, expect it to return (level, detail) or
    raise. A raised exception is recorded as a FAIL with the exception
    text — a broken individual check must never crash the whole
    preflight run."""
    def decorator(fn):
        try:
            level, detail = fn()
        except Exception as e:
            level, detail = "fail", f"Prüfung fehlgeschlagen: {e}"
        _results.append((level, name, detail))
        return fn
    return decorator


def _http_health(url: str, timeout: float = 2.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status == 200


def _load_config():
    from core.config import load_config
    return load_config()


def main():
    print("JARVIS Preflight-Check\n" + "=" * 40)

    try:
        config = _load_config()
    except Exception as e:
        print(f"{FAIL} config.yaml konnte nicht geladen werden: {e}")
        print("\nAbbruch — ohne Konfiguration sind keine weiteren Prüfungen möglich.")
        return 1

    # --- LLM server (llama-server, main 35B model) ---
    # core/llm_router.py hardcodes this endpoint (not read from
    # config.yaml) — kept in sync with that, not with llm.small.endpoint
    # (a different, smaller model on port 8081, checked separately below).
    @check("LLM-Hauptmodell (llama-server, Port 8080)")
    def _():
        base = "http://127.0.0.1:8080"
        try:
            if _http_health(f"{base}/health"):
                return "ok", base
        except Exception:
            pass
        return "warn", f"{base}/health nicht erreichbar — Hauptmodell evtl. noch nicht gestartet"

    # --- Small/fast LLM (quality gating, fast paths) ---
    @check("Kleines LLM (Quality-Gating)")
    def _():
        if not config.get("llm.small.enabled", True):
            return "ok", "in config.yaml deaktiviert"
        endpoint = config.get("llm.small.endpoint", "http://127.0.0.1:8081/v1/chat/completions")
        base = endpoint.split("/v1/")[0]
        try:
            if _http_health(f"{base}/health"):
                return "ok", base
        except Exception:
            pass
        return "warn", f"{base}/health nicht erreichbar"

    # --- Chatterbox TTS server ---
    @check("Chatterbox TTS-Server")
    def _():
        endpoint = config.get("tts.chatterbox_endpoint", "http://127.0.0.1:8765/tts")
        health_url = endpoint.rsplit("/tts", 1)[0] + "/health"
        try:
            if _http_health(health_url):
                return "ok", health_url
        except Exception:
            pass
        return "warn", f"{health_url} nicht erreichbar — Piper-Fallback wird verwendet"

    # --- STT model ---
    @check("Qwen3-ASR Modell")
    def _():
        model_dir = config.get("stt.qwen3.model_dir")
        if model_dir and Path(model_dir).is_dir():
            return "ok", model_dir
        return "fail", f"Modellverzeichnis fehlt: {model_dir}"

    # --- Audio input ---
    @check("Mikrofon (Audio-Eingabe)")
    def _():
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sources"],
                capture_output=True, text=True, timeout=3,
            )
            sources = [l for l in result.stdout.splitlines() if l.strip()]
            if sources:
                return "ok", f"{len(sources)} Quelle(n) gefunden"
            return "warn", "keine PulseAudio-Quellen gefunden"
        except FileNotFoundError:
            return "warn", "pactl nicht installiert — Prüfung übersprungen"

    # --- Audio output ---
    @check("Lautsprecher (Audio-Ausgabe)")
    def _():
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                capture_output=True, text=True, timeout=3,
            )
            sinks = [l for l in result.stdout.splitlines() if l.strip()]
            if sinks:
                return "ok", f"{len(sinks)} Senke(n) gefunden"
            return "warn", "keine PulseAudio-Senken gefunden"
        except FileNotFoundError:
            return "warn", "pactl nicht installiert — Prüfung übersprungen"

    # --- Memory DB path ---
    @check("Memory-Datenbank")
    def _():
        db_path = Path(config.get("conversational_memory.db_path",
                                   "/home/alex/jarvis-data/data/memory.db"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if os.access(db_path.parent, os.W_OK):
            return "ok", str(db_path)
        return "fail", f"Verzeichnis nicht beschreibbar: {db_path.parent}"

    # --- FAISS index path ---
    @check("FAISS-Index-Verzeichnis")
    def _():
        faiss_path = Path(config.get("conversational_memory.faiss_index_path",
                                      "/home/alex/jarvis-data/data/memory_faiss"))
        faiss_path.mkdir(parents=True, exist_ok=True)
        if os.access(faiss_path, os.W_OK):
            return "ok", str(faiss_path)
        return "fail", f"Verzeichnis nicht beschreibbar: {faiss_path}"

    # --- WSLInterop ---
    @check("WSL2-Umgebung")
    def _():
        try:
            version = Path("/proc/version").read_text().lower()
            if "microsoft" in version:
                return "ok", "läuft unter WSL2"
            return "warn", "kein WSL2 erkannt (/proc/version) — evtl. natives Linux"
        except Exception:
            return "warn", "/proc/version nicht lesbar"

    # --- Required paths ---
    @check("Datenpfade")
    def _():
        storage_path = Path(config.get("system.storage_path", "/home/alex/jarvis-data"))
        if storage_path.is_dir():
            return "ok", str(storage_path)
        return "fail", f"Storage-Pfad fehlt: {storage_path}"

    # --- Disk space ---
    @check("Freier Speicherplatz")
    def _():
        storage_path = Path(config.get("system.storage_path", "/home/alex/jarvis-data"))
        check_path = storage_path if storage_path.exists() else Path.home()
        usage = shutil.disk_usage(check_path)
        free_gb = usage.free / (1024 ** 3)
        if free_gb < 5:
            return "fail", f"nur noch {free_gb:.1f} GB frei"
        if free_gb < 20:
            return "warn", f"{free_gb:.1f} GB frei — wird knapp für Modelle/Logs"
        return "ok", f"{free_gb:.1f} GB frei"

    # --- Required executables ---
    @check("Benötigte Programme")
    def _():
        required = ["aplay", "ffmpeg"]
        optional = [
            config.get("stt.whisper_bin", "").replace("~", str(Path.home())),
            config.get("tts.piper_bin", "").replace("~", str(Path.home())),
            config.get("llm.local.llama_cli", "").replace("~", str(Path.home())),
        ]
        missing_required = [r for r in required if shutil.which(r) is None]
        missing_optional = [
            o for o in optional
            if o and not (shutil.which(o) or Path(o).is_file())
        ]
        if missing_required:
            return "fail", f"fehlt: {', '.join(missing_required)}"
        if missing_optional:
            return "warn", f"optional fehlend: {', '.join(missing_optional)}"
        return "ok", "aplay, ffmpeg vorhanden"

    # --- Report ---
    print()
    icon = {"ok": OK, "warn": WARN, "fail": FAIL}
    for level, name, detail in _results:
        print(f"{icon[level]} {name}: {detail}")

    n_fail = sum(1 for level, _, _ in _results if level == "fail")
    n_warn = sum(1 for level, _, _ in _results if level == "warn")

    print("\n" + "=" * 40)
    if n_fail:
        print(f"{FAIL} {n_fail} kritische(r) Fehler, {n_warn} Warnung(en) — "
              f"JARVIS wird vermutlich nicht sauber starten.")
        return 1
    if n_warn:
        print(f"{WARN} {n_warn} Warnung(en), keine kritischen Fehler — "
              f"JARVIS sollte starten, evtl. mit Einschränkungen (siehe oben).")
        return 0
    print(f"{OK} Alle Prüfungen bestanden — bereit zum Start.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
