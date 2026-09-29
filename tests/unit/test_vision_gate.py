"""VisionGate + PresenceDetector npu_sensor honesty / privacy-quiet frame grab."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import numpy as np
import pytest

from core import vision_gate as vg
from core.privacy_gate import (Capability, PrivacyMode, get_privacy_gate,
                               reset_privacy_gate_singleton_for_tests)
from core.vision_gate import VisionGate
from tests.unit.test_presence_npu_backend import (  # noqa: F401  (fixtures + helpers)
    _Config, _detector, _FakeBackend, cpu_sentinel, fake_backend)


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_privacy_gate_singleton_for_tests()
    yield
    reset_privacy_gate_singleton_for_tests()


class _Cfg:
    def __init__(self, gate):
        self._d = {"vision.presence.llm_gate": gate}

    def get(self, k, d=None):
        return self._d.get(k, d)


class _Router:
    def __init__(self):
        self.calls = []

    def chat(self, user_message, image_data=None):
        self.calls.append((user_message, image_data))
        return "Person am Schreibtisch"


def _gate(**kw):
    cfg = {"enabled": True, "cooldown_s": 120}
    cfg.update(kw)
    return VisionGate(_Cfg(cfg))


FRAME = np.zeros((720, 1920, 3), dtype=np.uint8)


def test_disabled_by_default_forwards_nothing():
    g = VisionGate(_Cfg({}))
    router = _Router()
    assert g.should_forward("DETECTED", False, 1000.0) == (False, "disabled")
    assert g.forward(FRAME, "DETECTED", router) is None
    assert router.calls == [] and g.forwarded == 0
    assert g.status()["suppressed"]["disabled"] >= 1


def test_privacy_mode_blocks():
    get_privacy_gate().enter(PrivacyMode.PRIVACY, actor="test")
    g = _gate()
    ok, reason = g.should_forward("DETECTED", False, 1000.0)
    assert not ok and reason == "privacy_webcam"


def test_proactive_observation_blocked(monkeypatch):
    gate = get_privacy_gate()
    real = gate.allow
    monkeypatch.setattr(gate, "allow", lambda c: False if c == Capability.PROACTIVE_OBSERVATION else real(c))
    ok, reason = _gate().should_forward("DETECTED", False, 1000.0)
    assert not ok and reason == "privacy_proactive_observation"


def test_cloud_route_needs_cloud_capability(monkeypatch):
    gate = get_privacy_gate()
    real = gate.allow
    monkeypatch.setattr(gate, "allow", lambda c: False if c == Capability.CLOUD_LLM else real(c))
    g = VisionGate(_Cfg({"enabled": True}), route_is_cloud=lambda: True)
    assert g.should_forward("DETECTED", False, 1.0) == (False, "privacy_cloud_llm")
    g2 = VisionGate(_Cfg({"enabled": True}), route_is_cloud=lambda: False)
    assert g2.should_forward("DETECTED", False, 1.0)[0] is True


def test_conversation_active_suppresses_and_irrelevant_event():
    g = _gate()
    assert g.should_forward("DETECTED", True, 1.0) == (False, "conversation_active")
    assert g.should_forward("ABSENT", False, 1.0) == (False, "event_not_relevant")


def test_cooldown_and_exactly_one_frame_per_event():
    g = _gate()
    router = _Router()
    assert g.forward(FRAME, "DETECTED", router, now=1000.0) == "Person am Schreibtisch"
    assert len(router.calls) == 1                      # exactly one image call
    assert router.calls[0][1]                          # base64 payload
    assert g.forward(FRAME, "DETECTED", router, now=1010.0) is None   # cooldown
    assert len(router.calls) == 1
    assert g.status()["suppressed"]["cooldown"] == 1
    assert g.forward(FRAME, "DETECTED", router, now=1200.0) is not None
    assert g.status()["forwarded"] == 2


def test_frame_downscaled_and_png(tmp_path):
    import base64
    import cv2
    b64 = _gate().select_frame(FRAME)
    img = cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[1] == 1280


def test_no_persistence(tmp_path, monkeypatch):
    saved = []
    monkeypatch.chdir(tmp_path)
    try:
        import core.tools.image_tools as it  # noqa
        monkeypatch.setattr(it, "save_tool_image", lambda *a, **k: saved.append(1), raising=False)
    except Exception:
        pass
    before = sorted(p.name for p in tmp_path.rglob("*"))
    g = _gate()
    g.forward(FRAME, "DETECTED", _Router(), now=5.0)
    assert saved == []
    assert sorted(p.name for p in tmp_path.rglob("*")) == before
    assert g.status()["persistence"] == "none"


def test_frame_dropped_when_primary_not_ready():
    class _Probing(_Router):
        state = "STARTING"

        def probe_role(self, role=None, **kw):
            return self.state
    g = _gate()
    router = _Probing()
    assert g.forward(FRAME, "DETECTED", router, now=1000.0) is None
    assert router.calls == [] and g.status()["suppressed"]["primary_not_ready"] == 1
    router.state = "READY"
    assert g.forward(FRAME, "DETECTED", router, now=1001.0) == "Person am Schreibtisch"


def test_frame_dropped_during_handover_swap(tmp_path, monkeypatch):
    from core import runtime_state
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path))
    runtime_state.write_handover({"state": "STOPPING_PRIMARY", "is_swapping": True})
    g = _gate()
    router = _Router()
    assert g.forward(FRAME, "DETECTED", router, now=1.0) is None
    assert router.calls == [] and g.status()["suppressed"]["primary_swapping"] == 1


def test_router_error_is_contained():
    class Bad:
        def chat(self, *a, **k):
            raise RuntimeError("down")
    g = _gate()
    assert g.forward(FRAME, "DETECTED", Bad(), now=1.0) is None
    assert "down" in g.status()["last_error"]


# --------------------------------------------------------------------------
# PresenceDetector integration
# --------------------------------------------------------------------------

def test_npu_sensor_ready_when_npu_and_camera(tmp_path, fake_backend, cpu_sentinel):
    det, _ = _detector(tmp_path, {"backend": "npu"})
    det._running = True
    det.ensure_backend()
    s = det.get_status()["npu_sensor"]
    assert s["state"] == "READY" and s["reason"] is None
    assert s["wake_signal"] == "NOT_IMPLEMENTED"
    assert s["live_camera_npu"] == "NOT_IMPLEMENTED"


def test_npu_sensor_degraded_on_cpu_fallback_and_camera(tmp_path, fake_backend, cpu_sentinel):
    fake_backend.fail_code = "npu_not_listed"
    det, webcam = _detector(tmp_path, {"backend": "npu"})
    det._running = True
    det.ensure_backend()
    s = det.get_status()["npu_sensor"]
    assert s["state"] == "DEGRADED" and "npu_not_listed" in s["reason"]
    fake_backend.fail_code = None
    det2, webcam2 = _detector(tmp_path, {"backend": "npu"}, camera=False)
    det2._running = True
    det2.ensure_backend()
    s2 = det2.get_status()["npu_sensor"]
    assert s2["state"] == "DEGRADED" and s2["reason"] == "camera_unavailable"


def test_npu_sensor_stopped(tmp_path, fake_backend, cpu_sentinel):
    det, _ = _detector(tmp_path, {"backend": "npu"})
    assert det.get_status()["npu_sensor"]["state"] == "STOPPED"


def _probe(tmp_path, monkeypatch):
    from core import runtime_state
    from scripts import runtime_status as rs
    monkeypatch.setenv("JARVIS_RUNTIME_STATE_DIR", str(tmp_path / "state"))
    return runtime_state, rs


def test_real_writer_output_roundtrips_into_probe(tmp_path, fake_backend, cpu_sentinel, monkeypatch):
    runtime_state, rs = _probe(tmp_path, monkeypatch)
    det, _ = _detector(tmp_path, {"backend": "npu"})
    det._running = True
    det.ensure_backend()
    det._publish_npu_sensor()
    record = runtime_state.read_component_status("npu-sensor")
    assert {"state", "reason", "active", "enabled", "wake_signal", "live_camera_npu"} <= set(record)
    finding = rs.probe_npu_sensor(None)
    assert finding.state == "READY" and "nicht implementiert" in finding.detail

    fake_backend.fail_code = "npu_not_listed"
    det2, _ = _detector(tmp_path, {"backend": "npu"})
    det2._running = True
    det2.ensure_backend()
    det2._publish_npu_sensor()
    finding = rs.probe_npu_sensor(None)
    assert finding.state == "DEGRADED" and "npu_not_listed" in finding.detail


def test_camera_unavailable_branch_publishes_and_republishes(tmp_path, fake_backend, cpu_sentinel, monkeypatch):
    runtime_state, rs = _probe(tmp_path, monkeypatch)
    det, _ = _detector(tmp_path, {"backend": "npu"}, camera=False)
    det._running = True
    det.ensure_backend()
    det._grab_frame = lambda: None            # no-frame branch of _check_presence
    det._check_presence()
    first = runtime_state.read_component_status("npu-sensor")
    assert first and first["reason"] == "camera_unavailable"
    det._check_presence()                      # unchanged and inside the interval: no rewrite
    assert runtime_state.read_component_status("npu-sensor")["updatedEpoch"] == first["updatedEpoch"]
    det._last_npu_publish_at -= runtime_state.NPU_SENSOR_REPUBLISH_S + 1
    det._check_presence()                      # unchanged but due: republished (freshness heartbeat)
    assert runtime_state.read_component_status("npu-sensor")["updatedEpoch"] > first["updatedEpoch"]


def test_status_contains_vision_gate_default_off(tmp_path, fake_backend, cpu_sentinel):
    det, _ = _detector(tmp_path)
    assert det.get_status()["vision_gate"]["enabled"] is False


def test_grab_frame_permission_error_is_quiet(tmp_path, fake_backend, cpu_sentinel, monkeypatch):
    det, webcam = _detector(tmp_path)
    import asyncio

    class _Loop:
        def is_running(self):
            return True
    webcam._loop = _Loop()

    def boom(coro, loop):
        coro.close()
        raise PermissionError("webcam capture denied by privacy gate")
    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", boom)
    errors, debugs = [], []
    det.logger = SimpleNamespace(error=lambda m, **k: errors.append(m),
                                 debug=lambda m, **k: debugs.append(m),
                                 info=lambda m, **k: None, warning=lambda m, **k: None)
    assert det._grab_frame() is None
    assert det._grab_frame() is None
    assert errors == []
    assert len(debugs) == 1          # once per privacy period


def test_detected_event_forwards_one_frame_when_enabled(tmp_path, fake_backend, cpu_sentinel):
    det, _ = _detector(tmp_path)
    det._vision_gate = _gate(cooldown_s=60)
    router = _Router()
    det.set_llm_router(router)
    det._greeting_allowed = lambda pid, now: False
    det._event_frame = FRAME
    det._handle_detection("p1", 0.9, 100.0)
    det._vision_thread.join(timeout=5)
    assert len(router.calls) == 1
    assert det.last_vision_note == "Person am Schreibtisch"
    det._event_frame = None
