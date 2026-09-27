"""Runtime supervisor probe: state derivation, heartbeat trust and the UI contract.

Deterministic tests against stubbed systemd/HTTP facts (no real services). The
state rules under test are the ones in scripts/runtime_status.py::derive_state.
"""

import json
import os
import re
import time
from types import SimpleNamespace

import pytest

from core import runtime_state
from scripts import check_chatterbox_runtime as chatterbox
from scripts import runtime_status as rs

UI_STATES = {"STARTING", "READY", "DEGRADED", "ERROR", "STOPPED", "OFFLINE", "NOT_IMPLEMENTED"}
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$")


def assert_ui_contract(snapshot):
    """Mirrors UI/src/lib/jarvis/runtime-control.ts::parseRuntimeSnapshot."""
    assert snapshot["state"] in UI_STATES
    reasons = snapshot["degradedReasons"]
    assert isinstance(reasons, list) and len(reasons) <= 64
    assert all(isinstance(r, str) and len(r) <= 500 for r in reasons)
    assert ISO.match(snapshot["updatedAt"])
    ids = set()
    assert len(snapshot["components"]) <= 64
    for component in snapshot["components"]:
        assert component["id"] not in ids
        ids.add(component["id"])
        assert component["state"] in UI_STATES
        assert len(component["name"]) <= 500 and len(component.get("detail", "")) <= 500
        assert set(component) <= {"id", "name", "state", "detail"}
    assert set(snapshot["capabilities"]) == {"start", "stop", "restart"}
    assert all(isinstance(v, bool) for v in snapshot["capabilities"].values())
    assert len(snapshot.get("detail", "")) <= 500
    json.dumps(snapshot, ensure_ascii=True)


class ConfigStub:
    def __init__(self, **values):
        self.values = {
            "llm.local.endpoint": "http://127.0.0.1:8080/v1/chat/completions",
            "llm.small.enabled": False,
            "mobility.enabled": False,
            "image_generation.enabled": False,
            "web.port": 8091,
        }
        self.values.update(values)

    def get(self, key, default=None):
        return self.values.get(key, default)


UNIT_ACTIVE = {"LoadState": "loaded", "ActiveState": "active", "SubState": "running", "MainPID": "", "InvocationID": ""}
UNIT_INACTIVE = {"LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead", "MainPID": "0", "InvocationID": ""}
UNIT_FAILED = {"LoadState": "loaded", "ActiveState": "failed", "SubState": "failed", "MainPID": "0", "InvocationID": ""}


@pytest.fixture
def world(monkeypatch, tmp_path):
    """A fully healthy world; tests break exactly one fact at a time."""
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("INVOCATION_ID", raising=False)
    monkeypatch.delenv("JARVIS_ALLOW_DEGRADED_TTS", raising=False)
    facts = {
        "config": ConfigStub(),
        "voice": dict(UNIT_ACTIVE, MainPID=str(os.getpid())),
        "llm_unit": dict(UNIT_ACTIVE, MainPID="410"),
        "llm_health": (True, ""),
        "stt": True,
        "chatterbox": (True, []),
    }
    monkeypatch.setattr(rs.dependencies, "Config", lambda: facts["config"])
    monkeypatch.setattr(rs, "unit_props", lambda unit: facts["voice"] if unit == rs.VOICE_UNIT else facts["llm_unit"])
    monkeypatch.setattr(rs.dependencies, "_check_llm", lambda endpoint: facts["llm_health"])
    monkeypatch.setattr(rs.dependencies, "_stt_model_present", lambda config: facts["stt"])
    monkeypatch.setattr(rs.chatterbox, "diagnose", lambda *a, **k: facts["chatterbox"])
    runtime_state.write_heartbeat(interval_seconds=10, pipeline_state="IDLE", listener_running=True, directory=tmp_path)
    facts["dir"] = tmp_path
    return facts


def component(snapshot, id):
    return next(c for c in snapshot["components"] if c["id"] == id)


# --- READY / DEGRADED ---------------------------------------------------------------------

def test_ready_only_when_all_required_components_are_verified(world):
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert snapshot["state"] == "READY"
    assert snapshot["degradedReasons"] == []
    assert snapshot["capabilities"] == {"start": False, "stop": True, "restart": True}
    assert component(snapshot, "voice-daemon")["state"] == "READY"
    assert component(snapshot, "web")["state"] == "NOT_IMPLEMENTED"


def test_flux_resting_state_and_web_do_not_degrade_ready(world, monkeypatch):
    world["config"] = ConfigStub(**{"image_generation.enabled": True})
    monkeypatch.setattr(rs.dependencies, "_get_json", lambda url, timeout=2.0: (_ for _ in ()).throw(OSError("closed")))
    snapshot = rs.collect()
    assert snapshot["state"] == "READY"
    assert component(snapshot, "flux")["state"] == "STOPPED"


def test_flux_ready_status_is_recognised(world, monkeypatch):
    world["config"] = ConfigStub(**{"image_generation.enabled": True})
    monkeypatch.setattr(rs.dependencies, "_get_json", lambda url, timeout=2.0: (200, {"status": "ready"}))
    assert component(rs.collect(), "flux")["state"] == "READY"
    monkeypatch.setattr(rs.dependencies, "_get_json", lambda url, timeout=2.0: (200, {"status": "loading"}))
    snapshot = rs.collect()
    assert component(snapshot, "flux")["state"] == "STARTING"
    assert snapshot["state"] == "READY"  # a loading on-demand service is not a runtime fault


def test_optional_small_llm_down_is_reported_but_does_not_degrade(world, monkeypatch):
    world["config"] = ConfigStub(**{"llm.small.enabled": True, "llm.small.endpoint": "http://127.0.0.1:8081/x"})
    monkeypatch.setattr(rs.dependencies, "_check_llm",
                        lambda endpoint: (True, "") if "8080" in endpoint else (False, "URLError"))
    snapshot = rs.collect()
    assert snapshot["state"] == "READY"
    assert snapshot["degradedReasons"] == []
    assert component(snapshot, "llm-small")["state"] == "OFFLINE"


def test_vvs_not_ready_is_degraded_and_unconfigured_vvs_is_reported(world, monkeypatch):
    world["config"] = ConfigStub(**{"mobility.enabled": True, "mobility.base_url": "http://127.0.0.1:8088"})
    monkeypatch.setattr(rs.dependencies, "_check_vvs", lambda url: "not_ready")
    snapshot = rs.collect()
    assert snapshot["state"] == "DEGRADED"
    assert component(snapshot, "vvs")["state"] == "DEGRADED"
    world["config"] = ConfigStub(**{"mobility.enabled": True, "mobility.base_url": "${WIMAEDV_VVS_BASE_URL}"})
    snapshot = rs.collect()
    assert component(snapshot, "vvs")["state"] == "NOT_IMPLEMENTED"
    assert snapshot["state"] == "READY"  # an unconfigured optional dependency is not a runtime fault


@pytest.mark.parametrize("fact,value,needle", [
    ("llm_health", (False, "URLError"), "Haupt-LLM"),
    ("stt", False, "STT-Modell"),
    ("chatterbox", (False, ["config_mismatch"]), "Chatterbox"),
])
def test_required_component_failure_is_degraded_never_ready(world, fact, value, needle):
    world[fact] = value
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert snapshot["state"] == "DEGRADED"
    assert any(needle in reason for reason in snapshot["degradedReasons"])


def test_required_llm_unit_stopped_is_degraded_with_stopped_component(world):
    world["llm_unit"] = UNIT_INACTIVE
    snapshot = rs.collect()
    assert snapshot["state"] == "DEGRADED"
    assert component(snapshot, "llm-main")["state"] == "STOPPED"


def test_chatterbox_unreachable_is_offline_and_contract_break_is_error(world):
    world["chatterbox"] = (False, ["health_unreachable"])
    assert component(rs.collect(), "chatterbox")["state"] == "OFFLINE"
    world["chatterbox"] = (False, ["anchor_sha"])
    detail = component(rs.collect(), "chatterbox")
    assert detail["state"] == "ERROR"
    assert "/" not in detail["detail"]  # no paths or hashes leak into the snapshot


def test_explicit_degraded_tts_makes_chatterbox_optional(world, monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOW_DEGRADED_TTS", "1")
    world["chatterbox"] = (False, ["health_unreachable"])
    snapshot = rs.collect()
    assert component(snapshot, "chatterbox")["state"] == "DEGRADED"
    assert snapshot["state"] == "DEGRADED"  # still surfaced to the user


# --- windows audio bridge (passive check, never plays or executes anything) ------------------

INTEROP_ENTRY = "enabled\ninterpreter /init\nflags: PF\noffset 0\nmagic 4d5a\nmask \n"


@pytest.fixture
def audio(world, monkeypatch, tmp_path):
    """A healthy Windows audio bridge: handler registered, daemon env with socket, programs on PATH."""
    import shutil
    import socket
    import tempfile

    short = tempfile.mkdtemp(prefix="jb")
    monkeypatch.setattr(rs, "BINFMT_WSLINTEROP", str(tmp_path / "WSLInterop"))
    (tmp_path / "WSLInterop").write_text(INTEROP_ENTRY, encoding="utf-8")
    sock_path = os.path.join(short, "interop.sock")
    server = socket.socket(socket.AF_UNIX)
    server.bind(sock_path)
    bin_dir = tmp_path / "winbin"
    bin_dir.mkdir()
    for program in ("powershell.exe", "wslpath"):
        (bin_dir / program).write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / program).chmod(0o755)
    proc_root = tmp_path / "proc"
    (proc_root / str(os.getpid())).mkdir(parents=True)
    env_file = proc_root / str(os.getpid()) / "environ"
    env_file.write_bytes(f"PATH={bin_dir}:/usr/bin\0WSL_INTEROP={sock_path}\0".encode())
    monkeypatch.setenv("JARVIS_PROC_ROOT", str(proc_root))
    world["config"] = ConfigStub(**{"audio.output_backend": "windows"})

    # The check must be passive: any process start is a bug.
    def forbidden(*args, **kwargs):
        raise AssertionError("audio probe must not start processes")
    monkeypatch.setattr(rs.subprocess, "run", forbidden)
    monkeypatch.setattr(rs.subprocess, "Popen", forbidden)
    yield SimpleNamespace(world=world, entry=tmp_path / "WSLInterop", env_file=env_file, bin_dir=bin_dir,
                          sock=sock_path, proc_root=proc_root)
    server.close()
    shutil.rmtree(short, ignore_errors=True)


def test_working_audio_bridge_keeps_runtime_ready(audio):
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert component(snapshot, "audio-bridge")["state"] == "READY"
    assert snapshot["state"] == "READY"


def test_missing_interop_handler_makes_runtime_degraded_with_concrete_reason(audio):
    audio.entry.unlink()
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert snapshot["state"] == "DEGRADED"  # never READY when JARVIS cannot produce output
    assert component(snapshot, "audio-bridge")["state"] == "DEGRADED"
    assert any(r.startswith("Windows-Audio-Brücke:") and "nicht registriert" in r for r in snapshot["degradedReasons"])
    assert snapshot["capabilities"] == {"start": False, "stop": True, "restart": True}


@pytest.mark.parametrize("content,needle", [
    ("disabled\ninterpreter /init\nmagic 4d5a\n", "deaktiviert oder ungültig"),
    ("enabled\ninterpreter /init\nflags: PF\n", "deaktiviert oder ungültig"),   # no MZ magic: corrupt entry
    ("", "deaktiviert oder ungültig"),
    ("\x00\x01garbage\xff", "deaktiviert oder ungültig"),
])
def test_disabled_or_corrupt_interop_entry_is_degraded(audio, content, needle):
    audio.entry.write_text(content, encoding="utf-8", errors="replace")
    snapshot = rs.collect()
    assert snapshot["state"] == "DEGRADED"
    assert needle in component(snapshot, "audio-bridge")["detail"]


def test_unreadable_interop_entry_is_degraded_not_a_crash(audio):
    audio.entry.unlink()
    audio.entry.mkdir()  # reading a directory raises an OSError that is not FileNotFoundError
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert snapshot["state"] == "DEGRADED"
    assert "nicht lesbar" in component(snapshot, "audio-bridge")["detail"]


def test_powershell_missing_from_daemon_path_is_degraded(audio):
    (audio.bin_dir / "powershell.exe").unlink()
    snapshot = rs.collect()
    assert snapshot["state"] == "DEGRADED"
    assert "powershell.exe" in component(snapshot, "audio-bridge")["detail"]


def test_non_executable_powershell_is_degraded(audio):
    (audio.bin_dir / "powershell.exe").chmod(0o644)
    assert component(rs.collect(), "audio-bridge")["state"] == "DEGRADED"


def test_stale_or_missing_wsl_interop_socket_alone_is_not_a_fault(audio, tmp_path):
    """Verified live: with the handler registered, powershell.exe runs from a service whose WSL_INTEROP
    socket is gone (or empty). Reporting it as DEGRADED would be a false alarm."""
    os.unlink(audio.sock)  # socket of the start session vanished
    assert component(rs.collect(), "audio-bridge")["state"] == "READY"
    regular = tmp_path / "not-a-socket"
    regular.write_text("x", encoding="utf-8")
    audio.env_file.write_bytes(f"PATH={audio.bin_dir}\0WSL_INTEROP={regular}\0".encode())
    assert component(rs.collect(), "audio-bridge")["state"] == "READY"
    audio.env_file.write_bytes(f"PATH={audio.bin_dir}\0WSL_INTEROP=\0".encode())
    assert component(rs.collect(), "audio-bridge")["state"] == "READY"
    audio.env_file.write_bytes(f"PATH={audio.bin_dir}\0".encode())  # variable absent
    assert rs.collect()["state"] == "READY"


def test_unreadable_daemon_environment_is_degraded(audio):
    audio.env_file.unlink()
    assert "nicht lesbar" in component(rs.collect(), "audio-bridge")["detail"]


def test_independent_audio_causes_are_all_reported_at_once(audio):
    audio.entry.unlink()
    (audio.bin_dir / "powershell.exe").unlink()
    (audio.bin_dir / "wslpath").unlink()
    audio.env_file.write_bytes(f"PATH={audio.bin_dir}\0".encode())  # no /usr/bin: a real wslpath would be found
    detail = component(rs.collect(), "audio-bridge")["detail"]
    for needle in ("nicht registriert", "powershell.exe", "wslpath"):
        assert needle in detail
    assert_ui_contract(rs.collect())


@pytest.mark.parametrize("main_pid", ["", "0", "-5", "abc", "../etc", "12 34"])
def test_invalid_main_pid_is_degraded_without_touching_the_filesystem(audio, main_pid):
    audio.world["voice"] = dict(UNIT_ACTIVE, MainPID=main_pid)
    detail = next(c for c in rs.collect()["components"] if c["id"] == "audio-bridge")["detail"]
    assert "nicht lesbar" in detail


def test_missing_or_empty_path_variable_is_degraded(audio):
    audio.env_file.write_bytes(f"WSL_INTEROP={audio.sock}\0".encode())  # no PATH at all
    assert "powershell.exe" in component(rs.collect(), "audio-bridge")["detail"]
    audio.env_file.write_bytes(f"PATH=\0WSL_INTEROP={audio.sock}\0".encode())  # empty PATH
    assert "powershell.exe" in component(rs.collect(), "audio-bridge")["detail"]


def test_combined_audio_details_stay_valid_json_within_the_ui_limit(audio):
    audio.entry.unlink()
    audio.env_file.write_bytes(b"")
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    text = json.dumps(snapshot)
    for forbidden in (str(audio.bin_dir), audio.sock, "/proc/", "/mnt/", "PATH="):
        assert forbidden not in text


def test_small_llm_and_audio_bridge_are_reported_together(audio, monkeypatch):
    audio.entry.unlink()
    audio.world["config"] = ConfigStub(**{"audio.output_backend": "windows", "llm.small.enabled": True,
                                          "llm.small.endpoint": "http://127.0.0.1:8081/x"})
    monkeypatch.setattr(rs.dependencies, "_check_llm",
                        lambda endpoint: (True, "") if "8080" in endpoint else (False, "URLError"))
    snapshot = rs.collect()
    assert snapshot["state"] == "DEGRADED"
    assert len(snapshot["degradedReasons"]) == 1     # only the required audio bridge degrades; small LLM is optional
    assert "Windows-Audio" in snapshot["degradedReasons"][0]
    assert {c["id"] for c in snapshot["components"] if c["state"] in ("DEGRADED", "OFFLINE")} == {"audio-bridge", "llm-small"}


def test_audio_probe_only_applies_to_the_windows_backend_and_a_running_daemon(audio):
    audio.entry.unlink()
    audio.world["config"] = ConfigStub(**{"audio.output_backend": "auto"})
    assert all(c["id"] != "audio-bridge" for c in rs.collect()["components"])
    audio.world["config"] = ConfigStub(**{"audio.output_backend": "windows"})
    audio.world["voice"] = UNIT_INACTIVE
    snapshot = rs.collect()
    assert snapshot["state"] == "STOPPED"
    assert all(c["id"] != "audio-bridge" for c in snapshot["components"])


def test_audio_probe_exception_is_a_contract_valid_error(audio, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(rs, "probe_audio", broken)
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert snapshot["state"] == "ERROR"
    assert snapshot["capabilities"] == {"start": False, "stop": False, "restart": False}


def test_audio_details_do_not_leak_paths_or_environment(audio):
    audio.entry.unlink()
    text = json.dumps(rs.collect())
    for forbidden in (str(audio.bin_dir), audio.sock, "/proc/", "/mnt/", "PATH="):
        assert forbidden not in text


# --- voice daemon liveness ------------------------------------------------------------------

def test_missing_heartbeat_is_not_ready(world):
    (world["dir"] / runtime_state.HEARTBEAT_FILE).unlink()
    snapshot = rs.collect()
    assert snapshot["state"] == "DEGRADED"
    assert "Kein Heartbeat" in snapshot["degradedReasons"][0]


def test_stale_heartbeat_is_not_ready(world, monkeypatch):
    real = time.time()
    monkeypatch.setattr(rs.time, "time", lambda: real + 31)  # tolerance is max(30, 3 * interval) = 30
    snapshot = rs.collect()
    assert snapshot["state"] == "DEGRADED"
    assert "Heartbeat ist" in component(snapshot, "voice-daemon")["detail"]


def test_fresh_heartbeat_within_tolerance_is_ready(world, monkeypatch):
    real = time.time()
    monkeypatch.setattr(rs.time, "time", lambda: real + 20)
    assert rs.collect()["state"] == "READY"


def test_heartbeat_from_another_process_or_invocation_is_rejected(world, monkeypatch):
    world["voice"] = dict(UNIT_ACTIVE, MainPID=str(os.getpid() + 1))
    assert component(rs.collect(), "voice-daemon")["state"] == "DEGRADED"
    world["voice"] = dict(UNIT_ACTIVE, MainPID=str(os.getpid()), InvocationID="new-run")
    monkeypatch.setenv("INVOCATION_ID", "old-run")
    runtime_state.write_heartbeat(interval_seconds=10, pipeline_state="IDLE", listener_running=True, directory=world["dir"])
    assert component(rs.collect(), "voice-daemon")["state"] == "DEGRADED"


def test_listener_not_running_is_not_ready(world):
    runtime_state.write_heartbeat(interval_seconds=10, pipeline_state="IDLE", listener_running=False, directory=world["dir"])
    snapshot = rs.collect()
    assert snapshot["state"] == "DEGRADED"
    assert "Listener" in component(snapshot, "voice-daemon")["detail"]


# --- STOPPED / STARTING / ERROR -------------------------------------------------------------

def test_stopped_only_when_the_voice_unit_is_really_inactive(world):
    world["voice"] = UNIT_INACTIVE
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert snapshot["state"] == "STOPPED"
    assert snapshot["capabilities"] == {"start": True, "stop": False, "restart": False}
    # LLM/Chatterbox keep running by design (stop.sh) and are still reported truthfully.
    assert component(snapshot, "llm-main")["state"] == "READY"


def test_not_installed_unit_is_stopped(world):
    world["voice"] = {"LoadState": "not-found", "ActiveState": "inactive"}
    assert rs.collect()["state"] == "STOPPED"


def test_failed_or_crash_looping_unit_is_error(world):
    world["voice"] = UNIT_FAILED
    snapshot = rs.collect()
    assert snapshot["state"] == "ERROR"
    assert snapshot["capabilities"] == {"start": True, "stop": True, "restart": True}
    world["voice"] = dict(UNIT_ACTIVE, ActiveState="activating", SubState="auto-restart")
    assert rs.collect()["state"] == "ERROR"


def test_activating_unit_is_starting(world):
    world["voice"] = dict(UNIT_ACTIVE, ActiveState="activating", SubState="start")
    snapshot = rs.collect()
    assert snapshot["state"] == "STARTING"
    assert snapshot["capabilities"] == {"start": False, "stop": False, "restart": False}


def test_controlled_start_in_progress_is_starting_even_if_units_look_stopped(world, monkeypatch):
    world["voice"] = UNIT_INACTIVE
    runtime_state.write_lifecycle(action="start", phase="running", pid=4242, directory=world["dir"])
    monkeypatch.setattr(rs, "pid_is_lifecycle_script", lambda pid: pid == 4242)
    snapshot = rs.collect()
    assert snapshot["state"] == "STARTING"
    assert "start" in snapshot["detail"]


def test_controlled_stop_in_progress_is_reported_not_faked_as_stopped(world, monkeypatch):
    runtime_state.write_lifecycle(action="stop", phase="running", pid=4242, directory=world["dir"])
    monkeypatch.setattr(rs, "pid_is_lifecycle_script", lambda pid: True)
    snapshot = rs.collect()
    assert snapshot["state"] == "DEGRADED"
    assert snapshot["degradedReasons"] == ["Ein kontrollierter Stop läuft."]


def test_aborted_lifecycle_is_error_not_starting_forever(world, monkeypatch):
    world["voice"] = UNIT_INACTIVE
    runtime_state.write_lifecycle(action="start", phase="running", pid=4242, directory=world["dir"])
    monkeypatch.setattr(rs, "pid_is_lifecycle_script", lambda pid: False)
    snapshot = rs.collect()
    assert snapshot["state"] == "ERROR"
    assert "abgebrochen" in snapshot["detail"]


def test_aborted_lifecycle_does_not_hide_a_verifiably_healthy_backend(world, monkeypatch):
    runtime_state.write_lifecycle(action="start", phase="running", pid=4242, directory=world["dir"])
    monkeypatch.setattr(rs, "pid_is_lifecycle_script", lambda pid: False)
    snapshot = rs.collect()
    assert snapshot["state"] == "DEGRADED"  # never a silent READY: the abort is surfaced
    assert "abgebrochen" in snapshot["degradedReasons"][0]
    assert snapshot["capabilities"]["stop"] is True


def test_no_lifecycle_request_is_offered_while_a_controlled_one_runs(world, monkeypatch):
    runtime_state.write_lifecycle(action="stop", phase="running", pid=4242, directory=world["dir"])
    monkeypatch.setattr(rs, "pid_is_lifecycle_script", lambda pid: True)
    assert rs.collect()["capabilities"] == {"start": False, "stop": False, "restart": False}


def test_pid_check_requires_a_shell_running_a_lifecycle_script(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_PROC_ROOT", str(tmp_path))
    cases = {
        "1": b"bash\0/x/start.sh\0", "2": b"/bin/bash\0/x/restart.sh\0", "3": b"vim\0start.sh\0",
        "4": b"sleep\0999\0start.sh\0", "5": b"bash\0/x/other.sh\0", "6": b"start.sh\0",
    }
    for pid, cmdline in cases.items():
        (tmp_path / pid).mkdir()
        (tmp_path / pid / "cmdline").write_bytes(cmdline)
    assert [rs.pid_is_lifecycle_script(int(p)) for p in cases] == [True, True, False, False, False, False]
    assert rs.pid_is_lifecycle_script(99) is False


def test_corrupt_state_field_types_do_not_crash_the_probe(world):
    (world["dir"] / runtime_state.HEARTBEAT_FILE).write_text(json.dumps(
        {"schema": 1, "pid": os.getpid(), "invocationId": "", "updatedEpoch": "x", "intervalSeconds": [1],
         "listenerRunning": True}), encoding="utf-8")
    (world["dir"] / runtime_state.LIFECYCLE_FILE).write_text(json.dumps(
        {"schema": 1, "action": "start", "phase": "running", "pid": "abc"}), encoding="utf-8")
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert snapshot["state"] in {"DEGRADED", "ERROR"}


def test_failed_start_keeps_error_until_backend_is_actually_running(world):
    world["voice"] = UNIT_INACTIVE
    runtime_state.write_lifecycle(action="start", phase="finished", result="ERROR",
                                  message="Start fehlgeschlagen (exit 1).", pid=1, directory=world["dir"])
    snapshot = rs.collect()
    assert snapshot["state"] == "ERROR"
    assert snapshot["detail"] == "Start fehlgeschlagen (exit 1)."
    # a later clean stop record clears it
    runtime_state.write_lifecycle(action="stop", phase="finished", result="STOPPED", pid=1, directory=world["dir"])
    assert rs.collect()["state"] == "STOPPED"


def test_old_error_record_does_not_override_a_running_healthy_backend(world):
    runtime_state.write_lifecycle(action="start", phase="finished", result="ERROR", message="x", pid=1, directory=world["dir"])
    assert rs.collect()["state"] == "READY"


def test_unreachable_systemd_is_a_contract_valid_error(world, monkeypatch):
    def broken(unit):
        raise RuntimeError("systemd user manager nicht erreichbar")
    monkeypatch.setattr(rs, "unit_props", broken)
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert snapshot["state"] == "ERROR"
    assert snapshot["components"] == []


def test_any_probe_exception_is_a_contract_valid_error_without_lifecycle_requests(world, monkeypatch):
    def broken(*args, **kwargs):
        raise PermissionError("anchor unreadable")
    monkeypatch.setattr(rs.chatterbox, "diagnose", broken)  # raised after the config/systemd block
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert snapshot["state"] == "ERROR"
    assert snapshot["capabilities"] == {"start": False, "stop": False, "restart": False}
    assert "PermissionError" in snapshot["detail"] and "anchor" not in snapshot["detail"]


def test_unreadable_config_is_error(world, monkeypatch):
    def broken():
        raise FileNotFoundError("config")
    monkeypatch.setattr(rs.dependencies, "Config", broken)
    assert rs.collect()["state"] == "ERROR"


# --- contract hygiene -----------------------------------------------------------------------

def test_long_details_are_truncated_to_the_ui_limit(world, monkeypatch):
    world["chatterbox"] = (False, ["config_mismatch"])
    monkeypatch.setitem(rs._CHATTERBOX_DETAIL, "config_mismatch", "x" * 900)
    assert_ui_contract(rs.collect())


def test_snapshot_never_exposes_required_flag_secrets_or_local_paths(world):
    text = json.dumps(rs.collect()).lower()
    assert "required" not in text
    for forbidden in ("token", "password", "api_key", "/home/alex", "/mnt/"):
        assert forbidden not in text


def test_capabilities_table():
    table = {s: rs.capabilities(s) for s in UI_STATES}
    assert table["OFFLINE"] == {"start": True, "stop": False, "restart": False}
    assert table["NOT_IMPLEMENTED"] == {"start": False, "stop": False, "restart": False}
    assert table["STARTING"] == {"start": False, "stop": False, "restart": False}
    assert table["READY"] == {"start": False, "stop": True, "restart": True}


# --- shared state files -----------------------------------------------------------------------

def test_lifecycle_record_roundtrip_and_validation(tmp_path):
    runtime_state.write_lifecycle(action="restart", phase="finished", result="READY", message="ok", pid=7, directory=tmp_path)
    record = runtime_state.read_lifecycle(tmp_path)
    assert (record["action"], record["phase"], record["result"], record["pid"]) == ("restart", "finished", "READY", 7)
    assert ISO.match(record["updatedAt"])
    with pytest.raises(ValueError):
        runtime_state.write_lifecycle(action="format-disk", phase="running", pid=1, directory=tmp_path)
    with pytest.raises(ValueError):
        runtime_state.write_lifecycle(action="start", phase="finished", result="GREAT", pid=1, directory=tmp_path)


def test_corrupt_or_foreign_schema_state_files_are_ignored(tmp_path):
    (tmp_path / runtime_state.HEARTBEAT_FILE).write_text("{not json", encoding="utf-8")
    (tmp_path / runtime_state.LIFECYCLE_FILE).write_text(json.dumps({"schema": 99}), encoding="utf-8")
    assert runtime_state.read_heartbeat(tmp_path) is None
    assert runtime_state.read_lifecycle(tmp_path) is None


def test_record_cli_writes_only_the_lifecycle_file(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path))
    assert runtime_state.main(["start", "running", "--pid", "31"]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == [runtime_state.LIFECYCLE_FILE]
    assert runtime_state.read_lifecycle(tmp_path)["pid"] == 31
    assert runtime_state.main(["rm -rf", "running"]) == 1


def test_record_writer_needs_only_the_standard_library(tmp_path):
    import subprocess
    import sys
    # -S -E: no site-packages, so yaml/dotenv/aiohttp cannot be what makes this work.
    code = "import runpy,sys; sys.argv=['x','start','running','--pid','5']; runpy.run_path('core/runtime_state.py', run_name='__main__')"
    result = subprocess.run([sys.executable, "-S", "-E", "-c", code], cwd=str(rs.ROOT), capture_output=True, text=True,
                            env={"JARVIS_RUNTIME_STATE_DIR": str(tmp_path)})
    assert result.returncode == 0, result.stderr
    assert runtime_state.read_lifecycle(tmp_path)["pid"] == 5


def test_probe_cli_requires_the_explicit_json_flag():
    with pytest.raises(SystemExit):
        rs.main([])
    with pytest.raises(SystemExit):
        rs.main(["--record-lifecycle", "start", "running"])  # the probe has no write path


# --- chatterbox structured diagnosis (no message parsing) ------------------------------------

def _chatterbox_env(tmp_path, anchor_bytes=b"voice"):
    import hashlib
    anchor = tmp_path / "anchor.wav"
    anchor.write_bytes(anchor_bytes)
    env = tmp_path / "chatterbox.env"
    env.write_text("\n".join([
        "CHATTERBOX_PORT=8765", "CHATTERBOX_LANGUAGE=de", "CHATTERBOX_TEMPO=0.89", "CHATTERBOX_EXAGGERATION=0.5",
        "CHATTERBOX_CFG_WEIGHT=0.5", "CHATTERBOX_TEMPERATURE=0.8", "CHATTERBOX_REPETITION_PENALTY=1.2",
        "CHATTERBOX_MIN_P=0.05", "CHATTERBOX_TOP_P=1.0", f"CHATTERBOX_AUDIO_PROMPT_PATH={anchor}",
        f"CHATTERBOX_AUDIO_PROMPT_SHA256={hashlib.sha256(b'voice').hexdigest()}",
    ]), encoding="utf-8")
    return env


def test_chatterbox_diagnose_codes(monkeypatch, tmp_path):
    env = _chatterbox_env(tmp_path)
    expected = chatterbox.expected_contract(chatterbox.parse_env_file(env))
    monkeypatch.setattr(chatterbox, "http_json", lambda url, timeout=2.0: {"status": "ok"} if url.endswith("/health") else dict(expected))
    assert chatterbox.diagnose(env) == (True, [])
    assert chatterbox.validate_once(env) == (True, [])

    monkeypatch.setattr(chatterbox, "http_json", lambda url, timeout=2.0: (_ for _ in ()).throw(OSError("refused")))
    assert chatterbox.diagnose(env) == (False, ["health_unreachable"])

    drifted = dict(expected, tempo=1.5)
    monkeypatch.setattr(chatterbox, "http_json", lambda url, timeout=2.0: {"status": "ok"} if url.endswith("/health") else drifted)
    assert chatterbox.diagnose(env) == (False, ["config_mismatch"])

    (tmp_path / "anchor.wav").write_bytes(b"tampered")
    assert "anchor_sha" in chatterbox.diagnose(env)[1]
    assert chatterbox.diagnose(tmp_path / "missing.env") == (False, ["env_missing"])


# --- watchdog heartbeat -----------------------------------------------------------------------

def _watchdog(tmp_path, monkeypatch, *, listener_running=True):
    from core.watchdog import Watchdog
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path))
    wd = object.__new__(Watchdog)
    wd._check_interval = 10
    wd._coordinator = SimpleNamespace(state=SimpleNamespace(name="IDLE"), running=True)
    wd._listener = SimpleNamespace(running=listener_running)
    wd.logger = SimpleNamespace(warning=lambda *a, **k: None)
    return wd


def test_watchdog_writes_heartbeat_with_pid_and_listener_state(tmp_path, monkeypatch):
    monkeypatch.setenv("INVOCATION_ID", "inv-1")
    wd = _watchdog(tmp_path, monkeypatch)
    wd._write_heartbeat()
    heartbeat = runtime_state.read_heartbeat(tmp_path)
    assert heartbeat["pid"] == os.getpid() and heartbeat["invocationId"] == "inv-1"
    assert heartbeat["listenerRunning"] is True and heartbeat["pipelineState"] == "IDLE"
    assert abs(heartbeat["updatedEpoch"] - time.time()) < 5


def test_watchdog_heartbeat_failure_never_breaks_the_watchdog(tmp_path, monkeypatch):
    wd = _watchdog(tmp_path, monkeypatch)
    blocker = tmp_path / "file"
    blocker.write_text("not a dir", encoding="utf-8")
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(blocker))
    wd._write_heartbeat()  # must swallow the OSError and only log a warning


# --- Primary/Expert LLM, handover and NPU sensor ---------------------------------------------

def _units(world, monkeypatch, **by_unit):
    """unit_props stub per unit name; unknown units are inactive."""
    facts = {rs.VOICE_UNIT: world["voice"]}
    facts.update(by_unit)
    monkeypatch.setattr(rs, "unit_props", lambda unit: facts.get(unit, UNIT_INACTIVE))


def test_llm_primary_is_required_and_llm_main_is_a_derived_compat_alias(world):
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    primary, alias = component(snapshot, "llm-primary"), component(snapshot, "llm-main")
    assert primary["state"] == alias["state"] == "READY"
    world["llm_unit"] = UNIT_INACTIVE
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert component(snapshot, "llm-primary")["state"] == component(snapshot, "llm-main")["state"] == "STOPPED"
    assert snapshot["state"] == "DEGRADED"
    assert len([r for r in snapshot["degradedReasons"] if "Haupt-LLM" in r]) == 1  # alias never counted twice


def test_primary_unit_and_endpoint_follow_llm_primary_config(world, monkeypatch):
    world["config"] = ConfigStub(**{"llm.primary.endpoint": "http://127.0.0.1:8090/v1/chat/completions",
                                    "llm.primary.unit": "llama-server-primary.service"})
    seen = {}
    monkeypatch.setattr(rs, "unit_props", lambda unit: seen.setdefault(unit, world["voice"] if unit == rs.VOICE_UNIT else UNIT_ACTIVE))
    monkeypatch.setattr(rs.dependencies, "_check_llm", lambda endpoint: (seen.setdefault("endpoint", endpoint) and True, ""))
    assert rs.collect()["state"] == "READY"
    assert "llama-server-primary.service" in seen and seen["endpoint"].endswith(":8090/v1/chat/completions")


def test_expert_llm_resting_stopped_does_not_degrade_ready(world, monkeypatch):
    world["config"] = ConfigStub(**{"handover.enabled": True})
    _units(world, monkeypatch, **{"llama-server-primary.service": UNIT_ACTIVE, "llama-server-expert.service": UNIT_INACTIVE})
    snapshot = rs.collect()
    assert snapshot["state"] == "READY"
    assert component(snapshot, "llm-expert")["state"] == "STOPPED"
    assert component(snapshot, "llm-primary")["state"] == "READY"


def test_expert_component_is_absent_without_any_expert_config(world):
    assert all(c["id"] != "llm-expert" for c in rs.collect()["components"])


def test_handover_is_a_controlled_transition_not_degraded(world, monkeypatch):
    world["config"] = ConfigStub(**{"handover.enabled": True, "llm.expert.endpoint": "http://127.0.0.1:8082/v1/chat/completions"})
    _units(world, monkeypatch, **{"llama-server-expert.service": UNIT_ACTIVE})  # primary stopped on purpose
    runtime_state.write_handover({"state": "EXPERT_RUNNING", "is_swapping": True}, world["dir"])
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    assert snapshot["state"] == "STARTING" and snapshot["degradedReasons"] == []
    assert component(snapshot, "llm-primary")["state"] == "STARTING"
    assert component(snapshot, "llm-main")["state"] == "STARTING"
    assert component(snapshot, "llm-expert")["state"] == "READY"
    assert snapshot["capabilities"] == {"start": False, "stop": False, "restart": False}


def test_handover_lifecycle_record_never_triggers_the_orphan_error(world, monkeypatch):
    runtime_state.write_lifecycle(action="handover", phase="running", pid=999999, directory=world["dir"])
    snapshot = rs.collect()
    assert snapshot["state"] == "READY"        # a "running" handover record is no orphaned start/stop script


def test_finished_or_stale_handover_record_is_no_transition(world, monkeypatch):
    runtime_state.write_handover({"state": "IDLE", "is_swapping": False}, world["dir"])
    assert rs.collect()["state"] == "READY"
    runtime_state.write_handover({"state": "STOPPING_PRIMARY", "is_swapping": True}, world["dir"])
    assert runtime_state.handover_in_progress(world["dir"]) is not None
    real = time.time
    monkeypatch.setattr(runtime_state.time, "time", lambda: real() + runtime_state.HANDOVER_MAX_AGE_S + 60)
    assert runtime_state.handover_in_progress(world["dir"]) is None   # stale record: not "swapping" forever


def test_npu_sensor_unknown_without_telemetry_is_not_implemented(world):
    snapshot = rs.collect()
    npu = component(snapshot, "npu-sensor")
    assert npu["state"] == "NOT_IMPLEMENTED"
    assert "nicht implementiert" in npu["detail"]
    assert snapshot["state"] == "READY"


@pytest.mark.parametrize("info,state,needle", [
    (dict(state="READY", reason=None, active="npu"), "READY", "NPU"),
    (dict(state="DEGRADED", reason="cpu_fallback: npu_driver_missing", active="cpu"), "DEGRADED", "npu_driver_missing"),
    (dict(state="STOPPED", reason="x", active=None, enabled=False), "STOPPED", "deaktiviert"),
    (dict(state="DEGRADED", reason="no_camera", active=None), "OFFLINE", "no_camera"),
    (dict(state="STOPPED", reason="backend not initialised", active=None), "STOPPED", "nicht gestartet"),
])
def test_npu_sensor_reflects_real_backend_telemetry(world, info, state, needle):
    runtime_state.write_npu_sensor(runtime_state.npu_sensor_record(**info), world["dir"])   # shared schema
    snapshot = rs.collect()
    assert_ui_contract(snapshot)
    npu = component(snapshot, "npu-sensor")
    assert npu["state"] == state and needle in npu["detail"]
    if state in ("READY", "DEGRADED"):
        assert "Wake-Signal" in npu["detail"]      # wake / live-camera NPU are never claimed


def test_stale_npu_telemetry_is_not_trusted(world, monkeypatch):
    runtime_state.write_npu_sensor(runtime_state.npu_sensor_record(state="READY", reason=None, active="npu"), world["dir"])
    real = time.time
    monkeypatch.setattr(rs.time, "time", lambda: real() + rs.NPU_STATUS_MAX_AGE_S + 5)
    npu = component(rs.collect(), "npu-sensor")
    assert npu["state"] == "NOT_IMPLEMENTED" and "veraltet" in npu["detail"]


def test_offline_npu_sensor_does_not_degrade_the_runtime(world):
    runtime_state.write_npu_sensor(runtime_state.npu_sensor_record(state="DEGRADED", reason="no_backend", active=None), world["dir"])
    snapshot = rs.collect()
    assert component(snapshot, "npu-sensor")["state"] == "OFFLINE"
    assert snapshot["state"] == "READY" and snapshot["degradedReasons"] == []


def test_component_status_roundtrip_and_name_sanitising(tmp_path):
    runtime_state.write_component_status("npu-sensor", {"active": "npu"}, tmp_path)
    assert runtime_state.read_component_status("npu-sensor", tmp_path)["active"] == "npu"
    assert runtime_state.read_component_status("other", tmp_path) is None
    runtime_state.write_component_status("../evil", {"x": 1}, tmp_path)    # cannot escape the state dir
    assert not any(p.parent != tmp_path for p in tmp_path.rglob("*.json"))
    with pytest.raises(ValueError):
        runtime_state.write_component_status("///", {}, tmp_path)


def test_watchdog_suppresses_llm_alarm_during_handover(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path))
    runtime_state.write_handover({"state": "RESTORING_PRIMARY", "is_swapping": True}, tmp_path)
    from core import watchdog as wd
    dog = wd.Watchdog.__new__(wd.Watchdog)
    dog.logger = __import__("logging").getLogger("t")
    dog._last_llm_check_ts, dog._llm_health_interval = 0.0, 0.0
    dog._llm_status, dog._llm_unhealthy_count = None, 5
    announced = []
    dog._announce = announced.append
    dog._emit_event = lambda *a, **k: announced.append("event")
    monkeypatch.setattr(wd.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not probe/alarm")))
    dog._check_llm_health()
    assert dog._llm_status == "handover" and dog._llm_unhealthy_count == 0 and announced == []
