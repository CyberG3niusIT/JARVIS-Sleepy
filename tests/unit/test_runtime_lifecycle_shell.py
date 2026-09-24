"""Deterministic lifecycle tests against fake systemd/ports, not a real E2E."""

import json
import os
import shutil
import socket
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _fake_bin(root: Path):
    bindir = root / "fake-bin"
    bindir.mkdir()
    scripts = {
        "systemctl": r'''#!/usr/bin/env python3
import json, os, sys
p = os.environ["FAKE_STATE_FILE"]
with open(p) as f: s = json.load(f)
a = sys.argv[1:]
if a[:1] == ["--user"]: a = a[1:]
cmd = a[0] if a else ""
def save():
    with open(p, "w") as f: json.dump(s, f)
if cmd == "show-environment":
    print("PATH=" + s["manager_path"])
    if s.get("manager_interop"): print("WSL_INTEROP=" + s["manager_interop"])
    sys.exit(0)
if cmd == "set-environment":
    s["manager_path"] = next(value[5:] for value in a[1:] if value.startswith("PATH="))
    save(); sys.exit(0)
if cmd == "import-environment":
    s["manager_interop"] = os.environ.get("WSL_INTEROP", "")
    save(); sys.exit(0)
def prop(unit, key):
    if unit == "jarvis.service":
        return {"LoadState":s["jarvis_load"], "FragmentPath":s["jarvis_fragment"], "ExecStart":s["jarvis_exec"], "ActiveState":"active" if s["jarvis_active"] else "inactive", "InvocationID":s["invocation"], "MainPID":"430"}[key]
    if unit == "chatterbox.service":
        return {"LoadState":"not-found", "FragmentPath":"", "ExecStart":"", "ActiveState":"inactive", "User":"", "MainPID":"0", "ControlGroup":""}[key]
    if unit == "jarvis-chatterbox.service":
        return {"LoadState":"loaded" if s["chat_started"] else "not-found", "FragmentPath":"/run/user/1002/systemd/transient/jarvis-chatterbox.service", "ExecStart":"path=/bin/bash ; argv[]=/bin/bash "+os.path.join(os.environ["FAKE_ROOT"],"start_chatterbox.sh"), "ActiveState":"active" if s["chat_started"] else "inactive", "MainPID":s.get("chat_main_pid", "420"), "ControlGroup":"/user.slice/user-1002.slice/user@1002.service/app.slice/jarvis-chatterbox.service", "WorkingDirectory":os.environ["FAKE_ROOT"]}[key]
    return {"LoadState":"loaded", "FragmentPath":"/home/alex/.config/systemd/user/llama-server.service", "ExecStart":os.environ.get("FAKE_LLM_EXECSTART", "path=/home/alex/llama.cpp/build/bin/llama-server --host 127.0.0.1 --port 8080"), "ActiveState":"active" if s["llm_active"] else "inactive", "MainPID":"410"}[key]
if cmd == "show":
    unit = a[1]; key = next(x.split("=",1)[1] for x in a if x.startswith("--property="))
    print(prop(unit, key)); sys.exit(0)
if cmd == "link":
    s["jarvis_load"]="loaded"; s["jarvis_fragment"]=os.path.join(os.environ["FAKE_ROOT"],"systemd/jarvis.service"); save(); sys.exit(0)
if cmd in ("start", "stop", "restart"):
    unit=a[1]; s["calls"].append(cmd+":"+unit)
    if unit == "jarvis.service":
        s["jarvis_active"] = cmd != "stop"
        if cmd != "stop":
            s["invocation"] = "run-"+str(len(s["calls"]))
            with open(os.path.join(os.environ["FAKE_PROC_ROOT"], "430", "environ"), "wb") as f:
                f.write(("PATH=" + s["manager_path"] + "\0WSL_INTEROP=" + s.get("manager_interop", "") + "\0").encode())
    elif unit == "llama-server.service": s["llm_active"] = cmd == "start"
    elif unit == "jarvis-chatterbox.service": s["chat_started"] = cmd == "start"
    save(); sys.exit(0)
if cmd == "is-active":
    unit=a[-1]; active=s["jarvis_active"] if unit == "jarvis.service" else s["chat_started"]
    sys.exit(0 if active else 3)
if cmd == "daemon-reload": sys.exit(0)
sys.exit(0)
''',
        "sudo": r'''#!/usr/bin/env python3
import os, sys
a=sys.argv[1:]
if a[:1] == ["-n"]: a=a[1:]
if a[:1] == ["true"]: sys.exit(0)
if a[:1] == ["systemctl"]:
    # Test cases reuse an existing Chatterbox process, so privileged service actions are not expected.
    print("not-found"); sys.exit(0)
sys.exit(0)
''',
"ss": r'''#!/usr/bin/env python3
import json, os, sys
port = "8765" if ":8765" in " ".join(sys.argv) else "8080"
pid = os.environ.get("FAKE_CHAT_PID", "420") if port == "8765" else os.environ.get("FAKE_LLM_PID", "410")
p=os.environ["FAKE_STATE_FILE"]
with open(p) as f: state=json.load(f)
if port == "8765" and os.environ.get("FAKE_NO_CHAT") == "1" and not state["chat_started"]: sys.exit(0)
if port == "8080" and not state["llm_active"]: sys.exit(0)
if port == "8080" and state.get("llm_delay", 0) > 0:
    state["llm_delay"] -= 1
    with open(p,"w") as f: json.dump(state,f)
    sys.exit(0)
print("State Recv-Q Send-Q Local Address:Port Peer Address:Port")
address = os.environ.get("FAKE_LLM_BIND", "127.0.0.1") if port == "8080" else "127.0.0.1"
if any(arg.startswith("-") and "p" in arg for arg in sys.argv): print(f"LISTEN 0 128 {address}:{port} 0.0.0.0:* users:((\\\"python3\\\",pid={pid},fd=3))")
else: print(f"LISTEN 0 128 {address}:{port} 0.0.0.0:*")
''',
        "readlink": r'''#!/usr/bin/env python3
import os, sys
target=sys.argv[-1]
if target.startswith(os.environ.get("FAKE_PROC_ROOT", "/fake-proc")+"/") and target.endswith("/exe"):
    pid=target.split("/")[-2]
    if pid == os.environ.get("FAKE_LLM_PID", "410"): print("/home/alex/llama.cpp/build/bin/llama-server")
    elif pid in (os.environ.get("FAKE_CHAT_PID", "420"), "420", "999"): print("/usr/bin/python3.12")
    else: print("/usr/bin/python3")
elif target == "/home/alex/chatterbox-venv/bin/python3": print("/usr/bin/python3.12")
else:
    print(os.path.realpath(target))
''',
        "tr": r'''#!/usr/bin/env python3
import os, sys
sys.stdin.buffer.read()
root=os.environ["FAKE_ROOT"]
print(root+"/tools/chatterbox_server.py "+root+"/jarvis_continuous.py")
''',
"journalctl": r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_STATE_FILE"]) as f: state = json.load(f)
invocation = next((arg.split("=", 1)[1] for arg in sys.argv if arg.startswith("_SYSTEMD_INVOCATION_ID=")), None)
if invocation is not None:
    state["listener_journal_checks"] = state.get("listener_journal_checks", 0) + 1
    with open(os.environ["FAKE_STATE_FILE"], "w") as f: json.dump(state, f)
    if invocation == state["invocation"] and os.environ.get("FAKE_LISTENER_READY", "1") == "1":
        print("Continuous listening active", flush=True)
        sys.stdout.write("X" * int(os.environ.get("FAKE_JOURNAL_PADDING_BYTES", "0")))
    elif invocation == "old-run" and os.environ.get("FAKE_OLD_LISTENER_READY") == "1":
        print("Continuous listening active")
elif os.environ.get("FAKE_OLD_LISTENER_READY") == "1":
    print("Continuous listening active")
if os.environ.get("FAKE_CHAT_GPU_ERROR") == "1" and "jarvis-chatterbox.service" in sys.argv:
    print("RuntimeError: No CUDA GPUs are available")
''',
        "python-runtime": r'''#!/usr/bin/env python3
import os, sys
args=" ".join(sys.argv[1:])
if "--llm-port" in args: print("8080"); sys.exit(0)
if "check_chatterbox_runtime.py" in args:
    if os.environ.get("FAKE_CHAT_HEALTH", "1") == "1": print("OK"); sys.exit(0)
    print("/health not ready"); sys.exit(1)
if "check_runtime_dependencies.py" in args and "--required" in args:
    if os.environ.get("FAKE_REQUIRED_FAIL") == "1": print("ERROR: required dependency"); sys.exit(1)
    if os.environ.get("FAKE_DEGRADED") == "1": print("DEGRADED: optional VVS")
    else: print("VVS /health und /ready sind bereit.")
    sys.exit(0)
if "check_runtime_dependencies.py" in args and "--llm-health" in args:
    if os.environ.get("FAKE_LLM_HEALTH", "1") == "1": print("LLM /health ist bereit."); sys.exit(0)
    print("LLM /health ist nicht bereit."); sys.exit(1)
sys.exit(2)
''',
        "sleep": "#!/bin/sh\nexit 0\n",
        "id": r'''#!/usr/bin/env python3
import sys
if sys.argv[1:] == ["-u", "alex"]: print("1002")
else: print("1002")
''',
        "systemd-run": r'''#!/usr/bin/env python3
import json, os, sys
p=os.environ["FAKE_STATE_FILE"]
with open(p) as f: s=json.load(f)
s["calls"].append("run:jarvis-chatterbox")
s["chat_started"]=True
with open(p,"w") as f: json.dump(s,f)
sys.exit(0)
''',
    }
    for name, content in scripts.items():
        path = bindir / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
    return bindir


def _sandbox(tmp_path):
    root = tmp_path / "checkout"
    (root / "systemd").mkdir(parents=True)
    for name in ("start.sh", "stop.sh", "restart.sh"):
        shutil.copy2(REPO / name, root / name)
    (root / "systemd/jarvis.service").write_text("unit", encoding="utf-8")
    bindir = _fake_bin(tmp_path)
    state_file = tmp_path / "state.json"
    state = {
        "jarvis_load": "loaded",
        "jarvis_fragment": str(root / "systemd/jarvis.service"),
        "jarvis_exec": f"path=/home/alex/jarvis-venv/bin/python3 ; argv[]={root}/jarvis_continuous.py",
        "jarvis_active": False,
        "llm_active": True,
        "chat_started": True,
        "chat_main_pid": "420",
        "llm_delay": 0,
        "invocation": "old-run",
        "manager_path": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "manager_interop": "",
        "calls": [],
    }
    state_file.write_text(json.dumps(state), encoding="utf-8")
    proc_root = tmp_path / "fake-proc"
    interop_socket = tmp_path / "interop.sock"
    sock = socket.socket(socket.AF_UNIX)
    sock.bind(str(interop_socket))
    sock.close()
    for pid in ("410", "420", "430", "999"):
        proc_pid = proc_root / pid
        proc_pid.mkdir(parents=True, exist_ok=True)
        (proc_pid / "cmdline").write_bytes(b"synthetic-test-process\0")
        (proc_pid / "status").write_text(f"Name:\tpython3\nPid:\t{pid}\nPPid:\t258\nUid:\t1002\t1002\t1002\t1002\n", encoding="utf-8")
        control_group = "/user.slice/user-1002.slice/user@1002.service/app.slice/jarvis-chatterbox.service" if pid == "420" else "/user.slice/foreign.service"
        (proc_pid / "cgroup").write_text(f"0::{control_group}\n", encoding="utf-8")
    for pid in ("420", "999"):
        (proc_root / pid / "cmdline").write_bytes(
            f"/home/alex/chatterbox-venv/bin/python3\0{root}/tools/chatterbox_server.py\0".encode()
        )
    (proc_root / "430" / "environ").write_bytes(
        ("PATH=" + state["manager_path"] + ":/mnt/c/Windows/System32/WindowsPowerShell/v1.0\0"
         + "WSL_INTEROP=" + str(interop_socket) + "\0").encode()
    )
    env = os.environ.copy()
    env.update({
        "PATH": str(bindir) + os.pathsep + env["PATH"],
        "FAKE_ROOT": str(root),
        "FAKE_STATE_FILE": str(state_file),
        "FAKE_PROC_ROOT": str(proc_root),
        "JARVIS_PROC_ROOT": str(proc_root),
        "JARVIS_RUNTIME_PYTHON": str(bindir / "python-runtime"),
        "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
        "FAKE_CHAT_PID": "420",
        "FAKE_LLM_PID": "410",
        "WSL_INTEROP": str(interop_socket),
    })
    (tmp_path / "runtime").mkdir()
    return root, state_file, env


def _invoke(root, env, action="start"):
    result = subprocess.run(["bash", str(root / f"{action}.sh")], env=env, text=True, capture_output=True, timeout=15)
    return result


def _state(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_cold_start_links_and_starts_only_backend(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    state = _state(state_file)
    state["jarvis_load"] = "not-found"
    state["jarvis_fragment"] = ""
    state["jarvis_active"] = False
    state_file.write_text(json.dumps(state), encoding="utf-8")
    result = _invoke(root, env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "READY:" in result.stdout
    assert _state(state_file)["calls"] == ["start:jarvis.service"]
    state = _state(state_file)
    assert state["manager_path"].endswith(":/mnt/c/Windows/System32/WindowsPowerShell/v1.0")
    assert state["manager_interop"] == env["WSL_INTEROP"]
    assert b"WSL_INTEROP=" + env["WSL_INTEROP"].encode() in (tmp_path / "fake-proc/430/environ").read_bytes()


def test_warm_start_is_idempotent_and_reuses_chatterbox(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    state = _state(state_file)
    state["jarvis_active"] = True
    state_file.write_text(json.dumps(state), encoding="utf-8")
    result = _invoke(root, env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "READY:" in result.stdout
    assert _state(state_file)["calls"] == []
    assert _state(state_file)["manager_path"].count("/mnt/c/Windows/System32/WindowsPowerShell/v1.0") == 1


def test_warm_start_repairs_missing_audio_environment_once(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    state = _state(state_file)
    state["jarvis_active"] = True
    state_file.write_text(json.dumps(state), encoding="utf-8")
    (tmp_path / "fake-proc/430/environ").write_bytes(b"PATH=/usr/bin\0")
    result = _invoke(root, env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert _state(state_file)["calls"] == ["restart:jarvis.service"]
    result = _invoke(root, env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert _state(state_file)["calls"] == ["restart:jarvis.service"]


def test_warm_start_reuses_inherited_interop_after_start_session_ends(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    state = _state(state_file)
    state["jarvis_active"] = True
    state_file.write_text(json.dumps(state), encoding="utf-8")
    (tmp_path / "fake-proc/430/environ").write_bytes(
        b"PATH=/usr/bin:/mnt/c/Windows/System32/WindowsPowerShell/v1.0\0"
        b"WSL_INTEROP=/run/WSL/previous-session_interop\0"
    )
    result = _invoke(root, env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert _state(state_file)["calls"] == []


def test_missing_session_interop_rejects_backend_start(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env.pop("WSL_INTEROP")
    result = _invoke(root, env)
    assert result.returncode != 0
    assert "Interop-Socket" in result.stdout
    assert _state(state_file)["calls"] == []


def test_listener_marker_match_consumes_complete_journal(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env["FAKE_JOURNAL_PADDING_BYTES"] = "262144"
    result = _invoke(root, env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "READY:" in result.stdout
    assert _state(state_file)["listener_journal_checks"] == 1


def test_listener_missing_marker_is_not_ready(tmp_path):
    root, _, env = _sandbox(tmp_path)
    env["FAKE_LISTENER_READY"] = "0"
    result = _invoke(root, env)
    assert result.returncode != 0
    assert "Listener-Bereitschaft" in result.stdout
    assert "READY:" not in result.stdout


def test_listener_marker_from_previous_invocation_is_rejected(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env["FAKE_LISTENER_READY"] = "0"
    env["FAKE_OLD_LISTENER_READY"] = "1"
    result = _invoke(root, env)
    assert result.returncode != 0
    assert "READY:" not in result.stdout
    assert _state(state_file)["invocation"] != "old-run"


def test_listener_ready_timeout_keeps_sixty_checks_and_cleanup(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env["FAKE_LISTENER_READY"] = "0"
    result = _invoke(root, env)
    assert result.returncode != 0
    state = _state(state_file)
    assert state["listener_journal_checks"] == 60
    assert state["calls"] == ["start:jarvis.service", "stop:jarvis.service"]


def test_foreign_chatterbox_port_owner_is_never_killed_or_replaced(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env["FAKE_CHAT_PID"] = "999"
    state = _state(state_file)
    state["chat_main_pid"] = "999"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    result = _invoke(root, env)
    assert result.returncode != 0
    assert "Port 8765" in result.stdout
    assert _state(state_file)["calls"] == []


def test_required_dependency_failure_rolls_back_only_new_services(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    state = _state(state_file)
    state["llm_active"] = False
    state_file.write_text(json.dumps(state), encoding="utf-8")
    env["FAKE_NO_LLM"] = "1"
    env["FAKE_REQUIRED_FAIL"] = "1"
    result = _invoke(root, env)
    assert result.returncode != 0
    calls = _state(state_file)["calls"]
    assert calls == ["start:llama-server.service", "stop:llama-server.service"]


def test_retry_after_failed_start_reaches_ready(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env["FAKE_REQUIRED_FAIL"] = "1"
    assert _invoke(root, env).returncode != 0
    env.pop("FAKE_REQUIRED_FAIL")
    result = _invoke(root, env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "READY:" in result.stdout


def test_degraded_optional_dependency_does_not_claim_ready(tmp_path):
    root, _, env = _sandbox(tmp_path)
    env["FAKE_DEGRADED"] = "1"
    result = _invoke(root, env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "DEGRADED:" in result.stdout
    assert "READY:" not in result.stdout


def test_stop_is_idempotent_and_preserves_model_dependencies(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    result = _invoke(root, env, "stop")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "STOPPED:" in result.stdout
    state = _state(state_file)
    assert state["calls"] == []
    assert state["llm_active"] is True


def test_restart_runs_verified_stop_then_full_start(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    state = _state(state_file)
    state["jarvis_active"] = True
    state_file.write_text(json.dumps(state), encoding="utf-8")
    result = _invoke(root, env, "restart")
    assert result.returncode == 0, result.stderr + result.stdout
    calls = _state(state_file)["calls"]
    assert calls == ["stop:jarvis.service", "start:jarvis.service"]


def test_chatterbox_cold_start_uses_existing_script_in_user_transient_unit(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env["FAKE_NO_CHAT"] = "1"
    state = _state(state_file)
    state["chat_started"] = False
    state_file.write_text(json.dumps(state), encoding="utf-8")
    result = _invoke(root, env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "READY:" in result.stdout
    assert _state(state_file)["calls"] == ["run:jarvis-chatterbox", "start:jarvis.service"]


def test_chatterbox_failure_rolls_back_only_new_transient_service(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env["FAKE_NO_CHAT"] = "1"
    env["FAKE_CHAT_HEALTH"] = "0"
    state = _state(state_file)
    state["chat_started"] = False
    state_file.write_text(json.dumps(state), encoding="utf-8")
    result = _invoke(root, env)
    assert result.returncode != 0
    assert "Chatterbox Health-Endpunkt" in result.stdout
    assert _state(state_file)["calls"] == [
        "run:jarvis-chatterbox", "stop:jarvis-chatterbox.service",
    ]


def test_chatterbox_gpu_failure_reports_safe_cause_and_cleans_up(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env["FAKE_NO_CHAT"] = "1"
    env["FAKE_CHAT_HEALTH"] = "0"
    env["FAKE_CHAT_GPU_ERROR"] = "1"
    state = _state(state_file)
    state["chat_started"] = False
    state_file.write_text(json.dumps(state), encoding="utf-8")
    result = _invoke(root, env)
    assert result.returncode != 0
    assert "keine CUDA-fähige GPU" in result.stdout
    assert _state(state_file)["calls"] == [
        "run:jarvis-chatterbox", "stop:jarvis-chatterbox.service",
    ]


def test_llm_delayed_bind_is_waited_for_without_duplicate_start(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    state = _state(state_file)
    state["llm_active"] = False
    state["llm_delay"] = 3
    state_file.write_text(json.dumps(state), encoding="utf-8")
    result = _invoke(root, env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "READY:" in result.stdout
    assert _state(state_file)["calls"] == ["start:llama-server.service", "start:jarvis.service"]


def test_active_llm_delayed_bind_is_waited_for_without_duplicate_start(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    state = _state(state_file)
    state["llm_delay"] = 3
    state_file.write_text(json.dumps(state), encoding="utf-8")
    result = _invoke(root, env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "READY:" in result.stdout
    assert _state(state_file)["calls"] == ["start:jarvis.service"]


def test_foreign_llm_port_owner_is_not_replaced_or_killed(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env["FAKE_LLM_PID"] = "999"
    result = _invoke(root, env)
    assert result.returncode != 0
    assert "LLM-Port" in result.stdout + result.stderr
    assert _state(state_file)["calls"] == []


def test_llm_unit_with_mismatched_port_is_rejected(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env["FAKE_LLM_EXECSTART"] = "path=/home/alex/llama.cpp/build/bin/llama-server --host 127.0.0.1 --port 9999"
    result = _invoke(root, env)
    assert result.returncode != 0
    assert "Config-Port" in result.stdout
    assert _state(state_file)["calls"] == []


def test_llm_listener_on_all_interfaces_is_rejected(tmp_path):
    root, state_file, env = _sandbox(tmp_path)
    env["FAKE_LLM_BIND"] = "0.0.0.0"
    result = _invoke(root, env)
    assert result.returncode != 0
    assert "Loopback-Adresse" in result.stdout
    assert _state(state_file)["calls"] == []
