"""Low-cost, request-time host telemetry for the desktop live view."""

from datetime import datetime, timezone
import threading
import time

import psutil


class LiveTelemetrySampler:
    """Sample CPU between requests and memory directly; never invent a first CPU value."""

    def __init__(self):
        self._lock = threading.Lock()
        self._previous_cpu = None

    @staticmethod
    def _cpu_totals(times):
        fields = times._asdict()
        total = sum(fields.values()) - fields.get("guest", 0) - fields.get("guest_nice", 0)
        idle = times.idle + getattr(times, "iowait", 0)
        return total, idle

    def sample(self):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            current = (*self._cpu_totals(psutil.cpu_times()), time.monotonic())
            previous = self._previous_cpu
            self._previous_cpu = current
            cpu_percent = None
            interval = None
            if previous is not None:
                total_delta = current[0] - previous[0]
                idle_delta = current[1] - previous[1]
                interval = round(current[2] - previous[2], 3)
                if total_delta > 0 and 0 <= idle_delta <= total_delta:
                    cpu_percent = round((1 - idle_delta / total_delta) * 100, 1)

        memory = psutil.virtual_memory()
        return {
            "observedAt": now,
            "source": "JARVIS-Host (Linux/WSL)",
            "cpuPercent": cpu_percent,
            "memoryPercent": round(memory.percent, 1),
            "memoryUsedBytes": memory.used,
            "memoryTotalBytes": memory.total,
            "sampleIntervalSeconds": interval,
        }
