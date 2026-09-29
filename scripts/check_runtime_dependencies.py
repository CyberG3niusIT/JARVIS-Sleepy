#!/usr/bin/env python3
"""Read-only required/optional dependency checks for the JARVIS start path."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import runtime_state
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


DEFAULT_LLM_ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"


def primary_endpoint(config) -> str:
    """Primary LLM endpoint: llm.primary.endpoint if configured, else the legacy llm.local.endpoint."""
    return runtime_state.primary_endpoint(config, DEFAULT_LLM_ENDPOINT)


LEGACY_LLM_UNIT = "llama-server.service"  # single-model unit; only an explicit compatibility fallback
DEFAULT_PRIMARY_UNIT = "llama-server-primary.service"
DEFAULT_EXPERT_UNIT = "llama-server-expert.service"
_UNIT_NAME = re.compile(r"^[A-Za-z0-9_.@:-]+\.service$")


def _valid_unit(name) -> str | None:
    name = str(name or "").strip()
    return name if _UNIT_NAME.fullmatch(name) else None


def primary_unit(config) -> str:
    """User unit of the Primary LLM (single source of truth for start.sh and the supervisor).

    Order: JARVIS_LLM_UNIT env override, llm.primary.unit, handover.units.primary, and only
    then the legacy single-model unit as compatibility fallback.
    """
    for candidate in (os.environ.get("JARVIS_LLM_UNIT"), config.get("llm.primary.unit", None),
                      config.get("handover.units.primary", None)):
        unit = _valid_unit(candidate)
        if unit:
            return unit
    if config.get("handover.enabled", False):
        return DEFAULT_PRIMARY_UNIT
    return LEGACY_LLM_UNIT


def expert_unit(config) -> str | None:
    """User unit of the Expert LLM if one is configured, else None."""
    for candidate in (config.get("llm.expert.unit", None), config.get("handover.units.expert", None)):
        unit = _valid_unit(candidate)
        if unit:
            return unit
    if config.get("handover.enabled", False):
        return DEFAULT_EXPERT_UNIT
    return None


LLM_WAIT_DEFAULT_S = 180
LLM_WAIT_MAX_S = 300


def llm_start_wait(config) -> int:
    """Seconds start.sh waits for the primary: handover.primary_start_timeout_s, capped at 300 (default 180)."""
    try:
        value = int(float(config.get("handover.primary_start_timeout_s", LLM_WAIT_DEFAULT_S)))
    except (TypeError, ValueError):
        return LLM_WAIT_DEFAULT_S
    return max(1, min(LLM_WAIT_MAX_S, value))


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


def _stt_model_present(config: Config) -> bool:
    stt_backend = config.get("stt.backend", "")
    stt_model = config.get("stt.qwen3.model_dir") if stt_backend == "qwen3" else config.get("stt.model_path")
    return bool(stt_model) and os.path.exists(os.path.expanduser(stt_model))


def _check_vvs(base_url: str) -> str:
    """Returns "ready", "not_ready" or "unreachable" for a configured VVS base URL."""
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
            return "not_ready"
        return "ready"
    except Exception:
        return "unreachable"


def check(config: Config) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    degraded: list[str] = []

    endpoint = primary_endpoint(config)
    llm_ok, llm_error = _check_llm(endpoint)
    if not llm_ok:
        failures.append(f"LLM /health nicht bereit ({llm_error}).")

    if not _stt_model_present(config):
        failures.append("Konfiguriertes STT-Modell fehlt.")

    if config.get("llm.small.enabled", False):
        small_endpoint = config.get("llm.small.endpoint", "")
        small_ok, _ = _check_llm(small_endpoint)
        if not small_ok:
            # Optional and merely absent: informational, never a degradation of the runtime.
            print("INFO: Optionales Small-LLM ist nicht erreichbar (kein Einfluss auf den Runtime-Zustand).")

    base_url = config.get("mobility.base_url", "")
    if config.get("mobility.enabled", False):
        if not base_url or "${" in base_url:
            degraded.append("VVS-URL ist nicht konfiguriert; School/Mobility bleibt eingeschränkt.")
        else:
            vvs = _check_vvs(base_url)
            if vvs == "ready":
                print("VVS /health und /ready sind bereit.")
            elif vvs == "not_ready":
                degraded.append("VVS /health oder /ready ist nicht bereit.")
            else:
                degraded.append("VVS /health oder /ready ist nicht erreichbar.")

    return failures, degraded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--required", action="store_true", help="Fehler bei nicht bereiten Pflichtdiensten.")
    parser.add_argument("--llm-port", action="store_true", help="Gibt nur den konfigurierten Loopback-LLM-Port aus.")
    parser.add_argument("--llm-health", action="store_true", help="Prüft ausschließlich den konfigurierten Loopback-LLM-Health-Endpunkt.")
    parser.add_argument("--llm-unit", action="store_true", help="Gibt die konfigurierte Primary-LLM-User-Unit aus.")
    parser.add_argument("--llm-wait", action="store_true", help="Gibt die Wartezeit (s) auf das Primary-LLM aus (max. 300).")
    parser.add_argument("--expert-unit", action="store_true", help="Gibt die konfigurierte Expert-LLM-User-Unit aus (leer, wenn keine).")
    args = parser.parse_args()
    try:
        config = Config()
        if args.llm_unit:
            print(primary_unit(config))
            return 0
        if args.llm_wait:
            print(llm_start_wait(config))
            return 0
        if args.expert_unit:
            print(expert_unit(config) or "")
            return 0
        if args.llm_port:
            endpoint_value = primary_endpoint(config)
            endpoint = urlsplit(endpoint_value)
            if not _is_safe_loopback_http_url(endpoint_value):
                raise ValueError("LLM endpoint is not a local HTTP endpoint")
            print(endpoint.port)
            return 0
        if args.llm_health:
            ok, _ = _check_llm(primary_endpoint(config))
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
