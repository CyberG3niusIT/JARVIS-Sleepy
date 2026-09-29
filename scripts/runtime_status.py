#!/usr/bin/env python3
"""Read-only JARVIS runtime probe: the WSL half of the native runtime supervisor.

Prints one JSON document that matches the UI's ``RuntimeControlSnapshot``:

    {"state", "degradedReasons": [str], "updatedAt", "components": [...],
     "capabilities": {"start", "stop", "restart"}, "detail"?}

The runtime state is derived here, in exactly one place (``derive_state``), from
facts only: systemd unit state, the services' own health endpoints, the voice
daemon's heartbeat and the lifecycle record written by start.sh/stop.sh/restart.sh.
Nothing is guessed and nothing is started or stopped by this script.

Runtime = the JARVIS backend (voice daemon). Its required dependencies are the
local LLM, the STT model and the canonical Chatterbox voice. ``stop.sh``
deliberately leaves the LLM and Chatterbox running, so STOPPED means "the voice
daemon is stopped"; the component list still reports the other services.

The only write path is ``core/runtime_state.py`` (a tiny lifecycle record used by
the lifecycle scripts); this probe never writes anything.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import runtime_state  # noqa: E402
from scripts import check_chatterbox_runtime as chatterbox  # noqa: E402
from scripts import check_runtime_dependencies as dependencies  # noqa: E402

READY, DEGRADED, ERROR = "READY", "DEGRADED", "ERROR"
STARTING, STOPPED, OFFLINE, NOT_IMPLEMENTED = "STARTING", "STOPPED", "OFFLINE", "NOT_IMPLEMENTED"

BINFMT_WSLINTEROP = "/proc/sys/fs/binfmt_misc/WSLInterop"
VOICE_UNIT = "jarvis.service"
PRIMARY_UNIT = "llama-server-primary.service"
EXPERT_UNIT = "llama-server-expert.service"
LIFECYCLE_SCRIPTS = ("start.sh", "stop.sh", "restart.sh")
MAX_TEXT = 500
MAX_ITEMS = 64
HEARTBEAT_MIN_TOLERANCE = 30.0
HEARTBEAT_INTERVAL_FACTOR = 3.0


def _text(value: str) -> str:
    return value if len(value) <= MAX_TEXT else value[: MAX_TEXT - 1] + "…"


class Finding:
    """One component reading. ``required`` and ``informational`` never leave this module.

    An informational finding is reported honestly but never contributes a degraded reason:
    it belongs to no lifecycle this runtime owns (jarvis-web).
    """

    def __init__(self, id: str, name: str, state: str, detail: str = "", *, required: bool = False,
                 informational: bool = False):
        self.id, self.name, self.state, self.detail, self.required = id, name, state, detail, required
        self.informational = informational

    def public(self) -> dict[str, str]:
        item = {"id": self.id, "name": self.name, "state": self.state}
        if self.detail:
            item["detail"] = _text(self.detail)
        return item


# -- facts ---------------------------------------------------------------------

def unit_props(unit: str) -> dict[str, str]:
    """systemd user-unit properties. Raises RuntimeError if the user manager is unreachable."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", unit,
             "--property=LoadState,ActiveState,SubState,MainPID,InvocationID"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"systemd user manager nicht erreichbar ({type(exc).__name__})") from exc
    if result.returncode != 0:
        raise RuntimeError("systemd user manager nicht erreichbar")
    props: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition("=")
        props[key] = value
    return props


def pid_is_lifecycle_script(pid: int) -> bool:
    proc_root = Path(os.environ.get("JARVIS_PROC_ROOT", "/proc"))
    try:
        argv = (proc_root / str(pid) / "cmdline").read_bytes().decode("utf-8", "replace").split("\0")
    except OSError:
        return False
    # "bash /path/start.sh": the interpreter is first, a lifecycle script is the program it runs.
    return len(argv) >= 2 and os.path.basename(argv[0]) in ("bash", "sh") and os.path.basename(argv[1]) in LIFECYCLE_SCRIPTS


def _num(value: Any, cast: Any, default: Any = 0) -> Any:
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def _unit_state(props: dict[str, str]) -> str:
    """Maps a systemd unit onto a component state (never READY: health decides that)."""
    if props.get("LoadState") != "loaded":
        return STOPPED
    active, sub = props.get("ActiveState", ""), props.get("SubState", "")
    if active == "failed" or sub == "auto-restart":
        return ERROR
    if active == "activating":
        return STARTING
    return "active" if active == "active" else STOPPED


# -- component probes ------------------------------------------------------------

def probe_voice(props: dict[str, str]) -> Finding:
    name = "JARVIS Voice-Daemon"
    unit = _unit_state(props)
    if props.get("LoadState") != "loaded":
        return Finding("voice-daemon", name, STOPPED, "jarvis.service ist nicht installiert.", required=True)
    if unit == ERROR:
        return Finding("voice-daemon", name, ERROR, "jarvis.service ist fehlgeschlagen oder startet nach einem Fehler neu.", required=True)
    if unit in (STARTING, STOPPED):
        return Finding("voice-daemon", name, unit, "", required=True)
    heartbeat = runtime_state.read_heartbeat()
    if heartbeat is None:
        return Finding("voice-daemon", name, DEGRADED, "Kein Heartbeat des Voice-Daemons; Liveness nicht bestätigt.", required=True)
    main_pid = props.get("MainPID", "")
    invocation = props.get("InvocationID", "")
    if str(heartbeat.get("pid")) != main_pid or (heartbeat.get("invocationId") and heartbeat.get("invocationId") != invocation):
        return Finding("voice-daemon", name, DEGRADED, "Heartbeat stammt nicht vom laufenden Voice-Daemon; Liveness nicht bestätigt.", required=True)
    tolerance = max(HEARTBEAT_MIN_TOLERANCE, HEARTBEAT_INTERVAL_FACTOR * _num(heartbeat.get("intervalSeconds"), float))
    age = time.time() - _num(heartbeat.get("updatedEpoch"), float)
    if age > tolerance:
        return Finding("voice-daemon", name, DEGRADED, f"Heartbeat ist {int(age)} s alt (Toleranz {int(tolerance)} s).", required=True)
    if not heartbeat.get("listenerRunning"):
        return Finding("voice-daemon", name, DEGRADED, "Voice-Daemon lebt, der Listener läuft aber nicht.", required=True)
    return Finding("voice-daemon", name, READY, "", required=True)


def primary_unit(config: Any) -> str:
    """User unit of the Primary LLM: env override, llm.primary.unit, handover unit, else the legacy unit."""
    # Same resolution as start.sh (--llm-unit): config first, legacy unit only as fallback.
    return dependencies.primary_unit(config)


def expert_unit(config: Any) -> str | None:
    """User unit of the Expert LLM; None if no expert is configured at all."""
    unit = dependencies.expert_unit(config)
    if unit:
        return unit
    if config.get("llm.expert.endpoint", None):
        return EXPERT_UNIT
    return None


def probe_llm_primary(config: Any, props: dict[str, str], handover: dict[str, Any] | None = None) -> Finding:
    name = "Haupt-LLM Primary (llama-server)"
    if handover:
        # Controlled transition: the primary is down on purpose and comes back on its own.
        return Finding("llm-primary", name, STARTING,
                       f"Expert-Handover läuft ({handover.get('state', '?')}); Primary wird wiederhergestellt.", required=True)
    unit = _unit_state(props)
    if unit in (STOPPED, ERROR, STARTING):
        detail = {STOPPED: "Primary-LLM-Unit ist nicht aktiv.", ERROR: "Primary-LLM-Unit ist fehlgeschlagen.", STARTING: "Primary-LLM-Unit startet."}[unit]
        return Finding("llm-primary", name, unit, detail, required=True)
    ok, why = dependencies._check_llm(dependencies.primary_endpoint(config))
    if ok:
        return Finding("llm-primary", name, READY, "", required=True)
    return Finding("llm-primary", name, ERROR, f"Unit aktiv, aber /health nicht bereit ({why}).", required=True)


def probe_llm_expert(config: Any, props: dict[str, str] | None, handover: dict[str, Any] | None = None) -> Finding | None:
    """Expert LLM: STOPPED is the normal resting state (like FLUX); it only runs during a handover."""
    if props is None:
        return None
    name = "Expert-LLM (Qwen)"
    unit = _unit_state(props)
    if unit == ERROR:
        return Finding("llm-expert", name, ERROR, "Expert-LLM-Unit ist fehlgeschlagen.")
    if unit == STARTING:
        return Finding("llm-expert", name, STARTING, "Expert-LLM lädt das Modell.")
    if unit == STOPPED:
        return Finding("llm-expert", name, STOPPED, "Läuft nur bei Bedarf (Expert-Handover).")
    endpoint = config.get("llm.expert.endpoint", None)
    ok, _ = dependencies._check_llm(endpoint) if endpoint else (False, "")
    if ok:
        return Finding("llm-expert", name, READY, "Expert-Handover aktiv." if handover else "")
    return Finding("llm-expert", name, STARTING, "Expert-LLM-Unit aktiv, /health noch nicht bereit.")


NPU_STATUS_MAX_AGE_S = runtime_state.NPU_SENSOR_MAX_AGE_S


def probe_npu_sensor(config: Any) -> Finding:
    """NPU presence sensor from real telemetry only (shared schema: runtime_state.npu_sensor_record).

    Keys: state, reason, active ("npu" | "cpu" | None), enabled, wake_signal, live_camera_npu.
    Without fresh telemetry the state is NOT_IMPLEMENTED (a stale record is reported as stale, never
    as a live state); nothing is guessed. NPU wake-signal and live-camera NPU are always named as
    not implemented.
    """
    name = "NPU-Sensor (Presence)"
    not_real = "NPU-Wake-Signal und Live-Kamera-NPU sind nicht implementiert."
    info = runtime_state.read_component_status(runtime_state.NPU_SENSOR)
    if info is None:
        return Finding("npu-sensor", name, NOT_IMPLEMENTED, "Keine Telemetrie vom Voice-Daemon. " + not_real)
    age = time.time() - _num(info.get("updatedEpoch"), float)
    if not 0 <= age <= NPU_STATUS_MAX_AGE_S:
        return Finding("npu-sensor", name, NOT_IMPLEMENTED,
                       f"Telemetrie veraltet ({int(age)} s alt); Zustand unbekannt. " + not_real)
    if info.get("enabled") is False:
        return Finding("npu-sensor", name, STOPPED, "Presence-Erkennung ist deaktiviert.")
    active = info.get("active")
    reason = str(info.get("fallback_reason") or info.get("reason") or "unbekannt")
    if info.get("state") == "STOPPED" and active is None:
        return Finding("npu-sensor", name, STOPPED, f"Presence-Sensor nicht gestartet ({reason}).")
    if active == "npu":
        if info.get("state") == "DEGRADED":
            return Finding("npu-sensor", name, DEGRADED, f"Face-Backend auf der NPU, Sensor eingeschränkt (Grund: {reason}). " + not_real)
        return Finding("npu-sensor", name, READY, "Face-Backend läuft auf der NPU. " + not_real)
    if active == "cpu":
        return Finding("npu-sensor", name, DEGRADED, f"CPU-Fallback statt NPU (Grund: {reason}). " + not_real)
    return Finding("npu-sensor", name, OFFLINE, f"Kein aktives Face-Backend (Grund: {reason}).")


def probe_stt(config: Any) -> Finding:
    ok = dependencies._stt_model_present(config)
    return Finding("stt-model", "STT-Modell", READY if ok else ERROR, "" if ok else "Konfiguriertes STT-Modell fehlt.", required=True)


_CHATTERBOX_DETAIL = {
    "health_unreachable": "Chatterbox /health nicht erreichbar.",
    "health_not_ok": "Chatterbox /health meldet nicht ok.",
    "config_unreachable": "Chatterbox /config nicht erreichbar oder ungültig.",
    "config_mismatch": "Chatterbox weicht von der kanonischen Voice-Konfiguration ab.",
    "anchor_missing": "Voice-Anker fehlt.",
    "anchor_sha": "Voice-Anker-Integritätsprüfung schlägt fehl.",
    "env_missing": "Chatterbox-Runtime-Konfiguration fehlt.",
    "env_invalid": "Chatterbox-Runtime-Konfiguration ungültig.",
}


def probe_chatterbox() -> Finding:
    name = "Chatterbox TTS"
    # Same explicit opt-in as check_chatterbox_runtime.py / start.sh.
    required = os.environ.get("JARVIS_ALLOW_DEGRADED_TTS") != "1"
    ok, codes = chatterbox.diagnose()
    if ok:
        return Finding("chatterbox", name, READY, "", required=required)
    unreachable = "health_unreachable" in codes
    detail = " ".join(_CHATTERBOX_DETAIL.get(code, code) for code in codes)
    if not required:
        return Finding("chatterbox", name, DEGRADED, detail + " (Piper-Degraded-Modus ausdrücklich erlaubt.)", required=False)
    return Finding("chatterbox", name, OFFLINE if unreachable and len(codes) == 1 else ERROR, detail, required=True)


def probe_llm_small(config: Any) -> Finding | None:
    if not config.get("llm.small.enabled", False):
        return None
    ok, _ = dependencies._check_llm(config.get("llm.small.endpoint", ""))
    return Finding("llm-small", "Small-LLM", READY if ok else OFFLINE, "" if ok else "Optionales Small-LLM ist nicht erreichbar.")


def probe_vvs(config: Any) -> Finding | None:
    if not config.get("mobility.enabled", False):
        return None
    name = "VVS School/Mobility"
    base_url = config.get("mobility.base_url", "")
    if not base_url or "${" in base_url:
        return Finding("vvs", name, NOT_IMPLEMENTED, "VVS-URL ist nicht konfiguriert.")
    result = dependencies._check_vvs(base_url)
    return {
        "ready": Finding("vvs", name, READY),
        "not_ready": Finding("vvs", name, DEGRADED, "VVS /health oder /ready ist nicht bereit."),
    }.get(result, Finding("vvs", name, OFFLINE, "VVS /health oder /ready ist nicht erreichbar."))


def probe_flux(config: Any) -> Finding | None:
    if not config.get("image_generation.enabled", False):
        return None
    port = config.get("image_generation.server_port", 8190)
    try:
        # services/flux_server.py reports {"status": "ready" | "loading"}, not "ok".
        status, payload = dependencies._get_json(f"http://127.0.0.1:{int(port)}/health")
        state = READY if status == 200 and payload.get("status") == "ready" else STARTING
        detail = "" if state == READY else "FLUX lädt das Modell."
    except Exception:
        # FLUX is swapped in on demand (core/gpu_swap.py); not running is the normal resting state.
        state, detail = STOPPED, "Läuft nur bei Bedarf (GPU-Swap)."
    return Finding("flux", "FLUX Bildgenerierung", state, detail)


def _daemon_environ(pid: str) -> dict[str, str] | None:
    if not pid.isdigit() or int(pid) <= 0:  # systemd reports "0" when there is no main process
        return None
    proc_root = Path(os.environ.get("JARVIS_PROC_ROOT", "/proc"))
    try:
        raw = (proc_root / pid / "environ").read_bytes()
    except (OSError, ValueError):
        return None
    env: dict[str, str] = {}
    for entry in raw.split(b"\0"):
        key, sep, value = entry.partition(b"=")
        if sep:
            env[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
    return env


def probe_audio(config: Any, voice_props: dict[str, str]) -> Finding | None:
    """Passive check of the Windows audio bridge (core/tts.py::_play_wav_windows).

    JARVIS plays through `powershell.exe` started from WSL, which needs the WSLInterop binfmt handler and
    powershell.exe/wslpath on the daemon's PATH. Nothing is executed or played here. Only relevant while the daemon runs with audio.output_backend=windows.
    """
    if str(config.get("audio.output_backend", "auto")) != "windows" or voice_props.get("ActiveState") != "active":
        return None
    name = "Windows-Audio-Brücke"

    # Independent causes are all reported, so fixing one does not just reveal the next.
    problems: list[str] = []
    try:
        entry = Path(BINFMT_WSLINTEROP).read_text(encoding="utf-8", errors="replace")
        lines = entry.splitlines()
        if not lines or lines[0].strip() != "enabled" or "magic 4d5a" not in entry.lower():
            problems.append("WSLInterop-Handler (binfmt_misc) ist deaktiviert oder ungültig.")
    except FileNotFoundError:
        problems.append("WSLInterop-Handler (binfmt_misc) ist nicht registriert; Windows-Programme wie powershell.exe sind aus WSL nicht ausführbar.")
    except OSError:
        problems.append("WSLInterop-Handler (binfmt_misc) ist nicht lesbar.")

    env = _daemon_environ(voice_props.get("MainPID", ""))
    if env is None:
        problems.append("Umgebung des Voice-Daemons ist nicht lesbar; Audio-Brücke nicht bestätigt.")
    else:
        # WSL_INTEROP is deliberately not required to point at a live socket: the daemon's copy belongs to the
        # short-lived wsl.exe session that ran start.sh and is gone minutes later, yet with the handler registered
        # /init falls back and powershell.exe still runs (verified 2026-09-25 from a transient systemd service
        # with the stale manager environment and with the variable empty).
        for program in ("powershell.exe", "wslpath"):
            if not shutil.which(program, path=env.get("PATH", "")):
                problems.append(f"{program} ist im PATH des Voice-Daemons nicht auffindbar.")
    if problems:
        return Finding("audio-bridge", name, DEGRADED, " ".join(problems), required=True)
    return Finding("audio-bridge", name, READY, "", required=True)


WEB_SCRIPT = "jarvis_web.py"
WEB_HEALTH_PATH = "/api/stats"
WEB_HEALTH_TIMEOUT_S = 2.0
DEFAULT_RUNTIME_PYTHON = "/home/alex/jarvis-venv/bin/python3"
_SS_PID = re.compile(r"pid=(\d+)")


def _web_listening_sockets() -> list[tuple[str, int, int | None]]:
    """All listening TCP sockets as (host, port, pid | None) from ``ss -ltnp``. Read-only.

    Raises OSError / SubprocessError if ss cannot be run.
    """
    result = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, timeout=5, check=False)
    if result.returncode != 0:
        raise OSError("ss failed")
    sockets: list[tuple[str, int, int | None]] = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        host, _, port = parts[3].rpartition(":")
        if not port.isdigit():
            continue
        match = _SS_PID.search(line)
        sockets.append((host, int(port), int(match.group(1)) if match else None))
    return sockets


def _web_health(port: int) -> tuple[int | None, str]:
    """GET /api/stats on loopback: (http status | None, reason). Never raises, sends no body.

    The bearer token is only forwarded from the environment when one is set.
    """
    headers = {"Accept": "application/json"}
    token = os.environ.get("JARVIS_WEB_AUTH_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"http://127.0.0.1:{int(port)}{WEB_HEALTH_PATH}", headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=WEB_HEALTH_TIMEOUT_S) as response:
            status = response.status
            if status != 200:
                return status, ""
            try:
                payload = json.loads(response.read(1_048_576).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return status, "antwort ist kein JSON"
            return (status, "") if isinstance(payload, dict) else (status, "antwort ist kein JSON-Objekt")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return None, type(exc).__name__


def _web_process_identity(pid: int) -> tuple[bool, bool]:
    """(is the project's jarvis_web.py run by the runtime python as this user, desktop mode flag).

    The process must run <ROOT>/jarvis_web.py with the runtime interpreter under the current uid.
    Anything unreadable or different is a foreign process.
    """
    proc_root = Path(os.environ.get("JARVIS_PROC_ROOT", "/proc"))
    try:
        argv = (proc_root / str(pid) / "cmdline").read_bytes().decode("utf-8", "replace").split("\0")
        while argv and argv[-1] == "":
            argv.pop()
        status = (proc_root / str(pid) / "status").read_text(encoding="utf-8", errors="replace")
        uid = next((line.split()[1] for line in status.splitlines() if line.startswith("Uid:")), "")
        exe = os.path.realpath(proc_root / str(pid) / "exe")
        if len(argv) < 2 or uid != str(os.getuid()):
            return False, False
        script = argv[1]
        if not os.path.isabs(script):
            script = os.path.join(os.readlink(proc_root / str(pid) / "cwd"), script)
    except OSError:
        return False, False
    runtime_python = os.environ.get("JARVIS_RUNTIME_PYTHON", DEFAULT_RUNTIME_PYTHON)
    same_script = os.path.realpath(script) == os.path.realpath(ROOT / WEB_SCRIPT)
    same_python = os.path.realpath(runtime_python) == exe
    return same_script and same_python, "--desktop-mode" in argv[2:]


def probe_web(config: Any) -> Finding:
    """jarvis-web from facts only: listener -> process identity -> loopback-only -> /api/stats.

    Informational: it has no lifecycle owner here, so OFFLINE/STOPPED (or any other reading)
    never degrades the runtime and never enables a lifecycle action.
    """
    name = "JARVIS Web-API"
    port = _num(config.get("web.port", 8091), int, 8091)

    def finding(state: str, detail: str = "") -> Finding:
        return Finding("web", name, state, detail, informational=True)

    try:
        sockets = _web_listening_sockets()
    except (OSError, subprocess.SubprocessError) as exc:
        return finding(NOT_IMPLEMENTED, f"Listener-Prüfung nicht möglich ({type(exc).__name__}).")
    on_port = [entry for entry in sockets if entry[1] == port]
    if not on_port:
        return finding(OFFLINE, f"Kein Listener auf Port {port}; jarvis-web läuft nicht.")
    pids = {pid for _, _, pid in on_port}
    if None in pids or len(pids) != 1:
        return finding(ERROR, f"Port {port} ist belegt, der Prozessbesitzer ist nicht eindeutig lesbar.")
    pid = next(iter(pids))
    identical, desktop = _web_process_identity(pid)
    if not identical:
        return finding(ERROR, f"Port {port} ist von einem anderen Prozess als {WEB_SCRIPT} belegt (PID {pid}).")
    exposed = sorted({f"{host}:{p}" for host, p, owner in sockets
                      if owner == pid and not (host.startswith("127.") or host in ("[::1]", "::1"))})
    if exposed:
        return finding(ERROR, "jarvis-web lauscht nicht ausschließlich auf Loopback: " + ", ".join(exposed[:3]) + ".")
    mode = "Desktop-Modus (schreibgeschützt)" if desktop else "Standardmodus"
    status, reason = _web_health(port)
    if status == 200 and not reason:
        return finding(READY, mode + ".")
    if status == 503:
        return finding(STARTING, f"Web-API initialisiert ihre Komponenten. {mode}.")
    if status in (401, 403):
        return finding(DEGRADED, "Web-API verlangt eine Anmeldung; Health ohne Token nicht prüfbar (JARVIS_WEB_AUTH_TOKEN).")
    if status is None:
        return finding(DEGRADED, f"Listener von {WEB_SCRIPT} vorhanden, {WEB_HEALTH_PATH} nicht erreichbar ({reason}).")
    if status >= 500:
        return finding(ERROR, f"{WEB_HEALTH_PATH} meldet HTTP {status}.")
    return finding(DEGRADED, f"{WEB_HEALTH_PATH} meldet {'HTTP ' + str(status) if not reason else reason}.")


DESKTOP_API_UNIT = "jarvis-desktop-api.service"
# Must equal jarvis_web.DESKTOP_MODE_PORT (tests/unit/test_desktop_api_lifecycle.py).
DESKTOP_API_PORT = 8092


def probe_desktop_api(props: dict[str, str]) -> Finding:
    """Read-only desktop API (jarvis_web.py --desktop-mode), owned by start.sh/stop.sh via its user unit.

    READY only if the unit is active, its MainPID is the one project process in desktop mode listening on
    127.0.0.1:DESKTOP_API_PORT (loopback only), and /api/stats answers 200. Optional for the runtime: when it
    is merely down the voice runtime stays READY; a broken or foreign listener degrades it.
    """
    name = "JARVIS Desktop-API"
    port = DESKTOP_API_PORT

    def finding(state: str, detail: str = "") -> Finding:
        return Finding("desktop-api", name, state, detail)

    if props.get("LoadState") != "loaded":
        return finding(STOPPED, f"{DESKTOP_API_UNIT} ist nicht installiert.")
    unit = _unit_state(props)
    if unit == ERROR:
        return finding(ERROR, f"{DESKTOP_API_UNIT} ist fehlgeschlagen oder startet nach einem Fehler neu.")
    if unit in (STARTING, STOPPED):
        return finding(unit)
    try:
        sockets = _web_listening_sockets()
    except (OSError, subprocess.SubprocessError) as exc:
        return finding(NOT_IMPLEMENTED, f"Listener-Prüfung nicht möglich ({type(exc).__name__}).")
    on_port = [entry for entry in sockets if entry[1] == port]
    if not on_port:
        return finding(STARTING, f"Unit aktiv, noch kein Listener auf 127.0.0.1:{port}.")
    pids = {pid for _, _, pid in on_port}
    main_pid = _num(props.get("MainPID"), int)
    if pids != {main_pid}:
        return finding(ERROR, f"Port {port} gehört nicht dem Hauptprozess von {DESKTOP_API_UNIT}.")
    identical, desktop = _web_process_identity(main_pid)
    if not identical or not desktop:
        return finding(ERROR, f"Port {port} ist nicht von {WEB_SCRIPT} --desktop-mode dieses Checkouts belegt.")
    exposed = sorted({f"{host}:{p}" for host, p, owner in sockets
                      if owner == main_pid and not (host.startswith("127.") or host in ("[::1]", "::1"))})
    if exposed:
        return finding(ERROR, "Desktop-API lauscht nicht ausschließlich auf Loopback: " + ", ".join(exposed[:3]) + ".")
    status, reason = _web_health(port)
    if status == 200 and not reason:
        return finding(READY, f"Schreibgeschützt, 127.0.0.1:{port}.")
    if status == 503 or status is None:
        return finding(STARTING, f"{WEB_HEALTH_PATH} noch nicht bereit ({'HTTP ' + str(status) if status else reason}).")
    return finding(ERROR, f"{WEB_HEALTH_PATH} meldet {'HTTP ' + str(status) if not reason else reason}.")


# -- derivation (the single place that decides the runtime state) -----------------

def derive_state(voice: Finding, findings: list[Finding], lifecycle: dict[str, Any] | None,
                 lifecycle_alive: bool, handover: dict[str, Any] | None = None) -> tuple[str, list[str], str]:
    """Returns (state, degradedReasons, detail) from facts only.

    ``handover`` is a live Primary<->Expert model handover (core/model_handover.py): a controlled
    transition (STARTING), never DEGRADED. Its lifecycle records (action "handover") are not
    start/stop scripts and never trigger the orphan logic.
    """
    lifecycle = lifecycle or {}
    if lifecycle.get("action") == "handover":
        lifecycle = {}
    running = lifecycle.get("phase") == "running"
    action = lifecycle.get("action", "")

    if running and lifecycle_alive:
        if action == "stop":
            return DEGRADED, ["Ein kontrollierter Stop läuft."], "Stop läuft."
        return STARTING, [], f"Kontrollierter {action or 'start'} läuft."
    orphan = ""
    if running:
        orphan = f"Der letzte Lifecycle-Vorgang ({action}) wurde abgebrochen."
        if voice.state != READY:
            return ERROR, [], orphan
        # The backend is verifiably healthy despite the killed script: report facts, keep the note.

    if voice.state == ERROR:
        return ERROR, [], voice.detail
    if voice.state == STARTING:
        return STARTING, [], "jarvis.service startet."
    if voice.state == STOPPED:
        if lifecycle.get("phase") == "finished" and lifecycle.get("result") == ERROR:
            return ERROR, [], str(lifecycle.get("message") or "Der letzte Start ist fehlgeschlagen.")
        return STOPPED, [], "JARVIS-Backend ist gestoppt."

    if handover:
        return STARTING, [], f"Kontrollierter Expert-Handover läuft ({handover.get('state', '?')})."

    reasons = [orphan] if orphan else []
    for finding in findings:
        # jarvis-web is reported but owned by no lifecycle here: it never contributes a reason.
        if finding.informational:
            continue
        # Optional findings (small LLM, NPU sensor, ...) that are merely OFFLINE never degrade the runtime.
        if finding.state == READY or (finding.state in (STOPPED, STARTING, NOT_IMPLEMENTED, OFFLINE) and not finding.required):
            continue
        reasons.append(_text(f"{finding.name}: {finding.detail or finding.state}"))
    return (DEGRADED if reasons else READY), reasons[:MAX_ITEMS], ""


def capabilities(state: str) -> dict[str, bool]:
    return {
        "start": state in (STOPPED, ERROR, OFFLINE),
        "stop": state in (READY, DEGRADED, ERROR),
        "restart": state in (READY, DEGRADED, ERROR),
    }


def snapshot(state: str, reasons: list[str], components: list[dict[str, str]], detail: str = "") -> dict[str, Any]:
    document: dict[str, Any] = {
        "state": state,
        "degradedReasons": [_text(reason) for reason in reasons[:MAX_ITEMS]],
        "updatedAt": runtime_state.iso_now(),
        "components": components[:MAX_ITEMS],
        "capabilities": capabilities(state),
    }
    if detail:
        document["detail"] = _text(detail)
    return document


def _probe_failed(exc: Exception) -> dict[str, Any]:
    # The probe itself is broken: offer no lifecycle request (same rule as the Windows side).
    document = snapshot(ERROR, [], [], f"Runtime-Probe nicht möglich ({type(exc).__name__}).")
    document["capabilities"] = {"start": False, "stop": False, "restart": False}
    return document


def collect() -> dict[str, Any]:
    try:
        config = dependencies.Config()
        voice_props = unit_props(VOICE_UNIT)
        llm_props = unit_props(primary_unit(config))
        expert_name = expert_unit(config)
        expert_props = unit_props(expert_name) if expert_name else None
        handover = runtime_state.handover_in_progress()

        voice = probe_voice(voice_props)
        primary = probe_llm_primary(config, llm_props, handover)
        findings = [voice, primary, probe_stt(config), probe_chatterbox()]
        findings += [f for f in (probe_llm_expert(config, expert_props, handover), probe_llm_small(config),
                                 probe_audio(config, voice_props), probe_vvs(config), probe_flux(config),
                                 probe_npu_sensor(config)) if f is not None]
        findings.append(probe_desktop_api(unit_props(DESKTOP_API_UNIT)))
        findings.append(probe_web(config))

        lifecycle = runtime_state.read_lifecycle()
        alive = bool(lifecycle and lifecycle.get("phase") == "running" and pid_is_lifecycle_script(_num(lifecycle.get("pid"), int)))
        state, reasons, detail = derive_state(voice, findings, lifecycle, alive, handover)
        components = [f.public() for f in findings]
        # Compat alias: UI/tests know the Primary LLM as "llm-main". Derived from the primary, never counted twice.
        components.insert(components.index(primary.public()) + 1, dict(primary.public(), id="llm-main"))
        document = snapshot(state, reasons, components, detail)
    except Exception as exc:
        return _probe_failed(exc)
    if alive:
        # One lifecycle at a time: no new request while a controlled one is running (also during stop).
        document["capabilities"] = {"start": False, "stop": False, "restart": False}
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--json", action="store_true", help="Runtime-Snapshot als JSON ausgeben.")
    mode.add_argument("--desktop-api-ready", action="store_true",
                      help="Readiness der Desktop-API (Exit 0 nur bei READY; eine Zeile Zustand und Detail).")
    args = parser.parse_args(argv)
    if args.desktop_api_ready:
        try:
            desktop = probe_desktop_api(unit_props(DESKTOP_API_UNIT))
        except RuntimeError as exc:
            print(f"{ERROR}: {exc}")
            return 1
        print(f"{desktop.state}: {desktop.detail}".rstrip(": "))
        return 0 if desktop.state == READY else 1
    print(json.dumps(collect(), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
