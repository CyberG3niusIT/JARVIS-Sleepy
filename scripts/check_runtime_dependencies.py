#!/usr/bin/env python3
"""Read-only required/optional dependency checks for the JARVIS start path."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.config import Config


def _get_json(url: str, timeout: float = 2.0) -> tuple[int, dict]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with opener.open(request, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _health_url(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    return urlunsplit((parts.scheme, parts.netloc, "/health", "", ""))


def _is_safe_loopback_http_url(endpoint: str) -> bool:
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        and parsed.username is None
        and parsed.password is None
        and "?" not in endpoint
        and "#" not in endpoint
        and not parsed.query
        and not parsed.fragment
        and port is not None
        and 1 <= port <= 65535
    )


def _check_llm(endpoint: str) -> tuple[bool, str]:
    try:
        if not _is_safe_loopback_http_url(endpoint):
            return False, "endpoint is not loopback HTTP"
        status, payload = _get_json(_health_url(endpoint))
        if status != 200 or payload.get("status") != "ok":
            return False, "health response is not ok"
    except Exception as exc:
        return False, type(exc).__name__
    return True, ""


def check(config: Config) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    degraded: list[str] = []

    endpoint = config.get("llm.local.endpoint", "http://127.0.0.1:8080/v1/chat/completions")
    llm_ok, llm_error = _check_llm(endpoint)
    if not llm_ok:
        failures.append(f"LLM /health nicht bereit ({llm_error}).")

    stt_backend = config.get("stt.backend", "")
    stt_model = config.get("stt.qwen3.model_dir") if stt_backend == "qwen3" else config.get("stt.model_path")
    if not stt_model or not os.path.exists(os.path.expanduser(stt_model)):
        failures.append("Konfiguriertes STT-Modell fehlt.")

    if config.get("llm.small.enabled", False):
        small_endpoint = config.get("llm.small.endpoint", "")
        small_ok, _ = _check_llm(small_endpoint)
        if not small_ok:
            degraded.append("Optionales Small-LLM ist nicht erreichbar.")

    base_url = config.get("mobility.base_url", "")
    if config.get("mobility.enabled", False):
        if not base_url or "${" in base_url:
            degraded.append("VVS-URL ist nicht konfiguriert; School/Mobility bleibt eingeschränkt.")
        else:
            base = base_url.rstrip("/")
            try:
                if not _is_safe_loopback_http_url(base):
                    raise ValueError("VVS URL is not loopback HTTP")
                health_status, health = _get_json(f"{base}/health")
                ready_status, ready = _get_json(f"{base}/ready")
                health_status_value = str(health.get("status", "")).lower()
                if (health_status != 200 or ready_status != 200 or ready.get("ready") is not True
                        or health.get("healthy") is False or health.get("ok") is False
                        or (health_status_value and health_status_value not in {"ok", "healthy"})):
                    degraded.append("VVS /health oder /ready ist nicht bereit.")
                else:
                    print("VVS /health und /ready sind bereit.")
            except Exception:
                degraded.append("VVS /health oder /ready ist nicht erreichbar.")

    return failures, degraded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--required", action="store_true", help="Fehler bei nicht bereiten Pflichtdiensten.")
    parser.add_argument("--llm-port", action="store_true", help="Gibt nur den konfigurierten Loopback-LLM-Port aus.")
    parser.add_argument("--llm-health", action="store_true", help="Prüft ausschließlich den konfigurierten Loopback-LLM-Health-Endpunkt.")
    args = parser.parse_args()
    try:
        config = Config()
        if args.llm_port:
            endpoint_value = config.get("llm.local.endpoint", "http://127.0.0.1:8080/v1/chat/completions")
            endpoint = urlsplit(endpoint_value)
            if not _is_safe_loopback_http_url(endpoint_value):
                raise ValueError("LLM endpoint is not a local HTTP endpoint")
            print(endpoint.port)
            return 0
        if args.llm_health:
            ok, _ = _check_llm(config.get("llm.local.endpoint", "http://127.0.0.1:8080/v1/chat/completions"))
            if ok:
                print("LLM /health ist bereit.")
                return 0
            print("LLM /health ist nicht bereit.")
            return 1
        failures, degraded = check(config)
    except Exception as exc:
        print(f"ERROR: Runtime-Konfiguration konnte nicht gelesen werden ({type(exc).__name__}).")
        return 1
    for message in failures:
        print(f"ERROR: {message}")
    for message in degraded:
        print(f"DEGRADED: {message}")
    if not failures and not degraded:
        print("Runtime-Abhängigkeiten bereit.")
    return 1 if args.required and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
