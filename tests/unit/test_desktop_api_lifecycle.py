"""Contract: process and port ownership of the read-only desktop API (see docs/DESKTOP_ARCHITECTURE.md).

- jarvis_web.py --desktop-mode owns 127.0.0.1:DESKTOP_MODE_PORT; the standard web process keeps web.port.
- Lifecycle owner is systemd/jarvis-desktop-api.service, linked/started by start.sh and stopped by stop.sh.
- The native client (WindowsApp/JarvisApiClient.cs) talks to exactly that port.
"""
import configparser
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UNIT = ROOT / "systemd" / "jarvis-desktop-api.service"


def _unit():
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(UNIT, encoding="utf-8")
    return parser


def _web_port():
    text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    return int(re.search(r"^web:\s*\n\s+port:\s*(\d+)", text, re.MULTILINE).group(1))


def test_desktop_api_has_its_own_port_separate_from_the_standard_web_port():
    import jarvis_web
    from scripts import runtime_status
    assert jarvis_web.DESKTOP_MODE_HOST == "127.0.0.1"
    assert jarvis_web.DESKTOP_MODE_PORT == runtime_status.DESKTOP_API_PORT
    assert jarvis_web.DESKTOP_MODE_PORT != _web_port()
    client = (ROOT / "WindowsApp" / "JarvisApiClient.cs").read_text(encoding="utf-8")
    assert int(re.search(r"public const int LoopbackPort = (\d+);", client).group(1)) == jarvis_web.DESKTOP_MODE_PORT


@pytest.mark.parametrize("port,refused", [(8092, True), (8091, False), (9000, False)])
def test_standard_mode_cannot_take_the_desktop_port(port, refused):
    import jarvis_web
    assert (jarvis_web._standard_mode_port_problem(port) is not None) is refused


def test_unit_runs_this_checkouts_desktop_mode_with_recovery():
    unit = _unit()
    service = unit["Service"]
    exec_start = service["ExecStart"]
    assert exec_start.startswith("/home/alex/jarvis-venv/bin/python3 ")
    assert exec_start.endswith("/jarvis_web.py --desktop-mode")
    # The port and host are fixed by --desktop-mode itself; the unit must not try to widen them.
    assert "--port" not in exec_start and "--host" not in exec_start and "--voice" not in exec_start
    assert service["Restart"] == "on-failure"
    assert service["WorkingDirectory"] == str(Path(exec_start.split()[1]).parent)
    assert "jarvis.service" in unit["Unit"]["After"]


def test_unit_uses_the_same_checkout_and_interpreter_as_the_voice_unit():
    voice = configparser.ConfigParser(interpolation=None, strict=False)
    voice.optionxform = str
    voice.read(ROOT / "systemd" / "jarvis.service", encoding="utf-8")
    assert _unit()["Service"]["WorkingDirectory"] == voice["Service"]["WorkingDirectory"]
    assert _unit()["Service"]["ExecStart"].split()[0] == voice["Service"]["ExecStart"].split()[0]


def test_lifecycle_scripts_own_the_desktop_unit():
    start = (ROOT / "start.sh").read_text(encoding="utf-8")
    stop = (ROOT / "stop.sh").read_text(encoding="utf-8")
    assert "desktop_unit=jarvis-desktop-api.service" in start
    assert "scripts/runtime_status.py --desktop-api-ready" in start
    assert '"$execstart" == *"--desktop-mode"*' in start
    assert "desktop_unit=jarvis-desktop-api.service" in stop
    # stop.sh stops the reader before the writer.
    assert stop.index("systemctl --user stop $desktop_unit") < stop.index("systemctl --user stop jarvis.service")
