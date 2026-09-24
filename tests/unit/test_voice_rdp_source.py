"""The PortAudio pulse device is not a PulseAudio source name."""

import subprocess
from types import SimpleNamespace

from core.continuous_listener import ContinuousListener


def test_virtual_pulse_device_accepts_rdp_source_without_reset(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command == ["pactl", "get-default-source"]:
            return SimpleNamespace(stdout="RDPSource\n")
        if command == ["pactl", "get-source-volume", "@DEFAULT_SOURCE@"]:
            return SimpleNamespace(stdout="100%")
        raise AssertionError(f"unexpected pactl command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    listener = ContinuousListener.__new__(ContinuousListener)
    listener.device = "pulse"
    listener.logger = SimpleNamespace(warning=lambda *args: None,
                                      info=lambda *args: None,
                                      debug=lambda *args: None)

    listener._check_pipewire_source()

    assert calls == [
        ["pactl", "get-default-source"],
        ["pactl", "get-source-volume", "@DEFAULT_SOURCE@"],
    ]
