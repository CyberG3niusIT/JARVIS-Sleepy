from collections import namedtuple

from core.live_telemetry import LiveTelemetrySampler


CpuTimes = namedtuple("CpuTimes", "user nice system idle iowait")


def test_cpu_is_unavailable_until_two_real_samples(monkeypatch):
    cpu_samples = iter([CpuTimes(10, 0, 5, 80, 5), CpuTimes(12, 0, 6, 90, 7)])
    monkeypatch.setattr("core.live_telemetry.psutil.cpu_times", lambda: next(cpu_samples))
    monkeypatch.setattr(
        "core.live_telemetry.psutil.virtual_memory",
        lambda: type("Memory", (), {"percent": 42.5, "used": 425, "total": 1000})(),
    )
    sampler = LiveTelemetrySampler()

    first = sampler.sample()
    second = sampler.sample()

    assert first["cpuPercent"] is None
    assert second["cpuPercent"] == 20.0
    assert second["sampleIntervalSeconds"] is not None
    assert first["memoryPercent"] == second["memoryPercent"] == 42.5
    assert first["source"] == "JARVIS-Host (Linux/WSL)"
    assert first["observedAt"]
