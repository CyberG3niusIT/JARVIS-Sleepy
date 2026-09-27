"""Presence NPU backend: SCRFD decoding, backend selection/fallback, camera state.

Hardware-free tests use a fake backend. The final test (``test_real_npu_smoke``)
runs the real Windows OpenVINO worker on the Intel NPU and is skipped unless

  JARVIS_NPU_WINDOWS_PYTHON   Windows python.exe with numpy + openvino
  JARVIS_NPU_SMOKE_PHOTOS     folder with face photos (jpg/png), never modified
  JARVIS_NPU_MODEL_DIR        buffalo_l dir with det_10g.onnx + w600k_r50.onnx
                              (default /home/alex/jarvis-data/models/insightface/buffalo_l)
"""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from core import npu_face_backend as nfb
from core import presence_detector as pd
from core.npu_face_backend import NpuFace, NpuUnavailable, decode_scrfd


# --------------------------------------------------------------------------
# SCRFD decoding
# --------------------------------------------------------------------------

def _empty_outputs():
    outs = []
    for width in (1, 4, 10):
        for stride in nfb.FEAT_STRIDES:
            n = (640 // stride) ** 2 * nfb.NUM_ANCHORS
            outs.append(np.zeros((n, width), dtype=np.float32))
    return outs


def test_decode_scrfd_empty_below_threshold():
    outs = _empty_outputs()
    outs[0][10, 0] = 0.49  # just below det_thresh
    dets, kps = decode_scrfd(outs, det_scale=1.0)
    assert dets.shape == (0, 5) and kps.shape == (0, 5, 2)


def test_decode_scrfd_box_keypoints_and_scale():
    outs = _empty_outputs()
    stride = 8
    grid = 640 // stride
    idx = (10 * grid + 20) * nfb.NUM_ANCHORS   # grid cell (row 10, col 20), first anchor
    outs[0][idx, 0] = 0.9
    outs[3][idx] = [2, 3, 4, 5]                # distances in stride units
    outs[6][idx] = np.arange(10, dtype=np.float32)
    dets, kps = decode_scrfd(outs, det_scale=0.5)
    cx, cy = 20 * stride, 10 * stride
    assert dets.shape == (1, 5)
    np.testing.assert_allclose(
        dets[0, :4],
        np.array([cx - 2 * stride, cy - 3 * stride, cx + 4 * stride, cy + 5 * stride]) / 0.5,
    )
    assert dets[0, 4] == pytest.approx(0.9)
    np.testing.assert_allclose(kps[0, 0], np.array([cx + 0 * stride, cy + 1 * stride]) / 0.5)


def test_decode_scrfd_nms_merges_overlapping_duplicates():
    outs = _empty_outputs()
    stride = 8
    grid = 640 // stride
    for col, score in ((20, 0.9), (21, 0.8)):  # neighbouring anchors, nearly the same box
        idx = (10 * grid + col) * nfb.NUM_ANCHORS
        outs[0][idx, 0] = score
        outs[3][idx] = [5, 5, 5, 5]
    dets, _ = decode_scrfd(outs, det_scale=1.0)
    assert len(dets) == 1 and dets[0, 4] == pytest.approx(0.9)


def test_npu_face_normed_embedding_is_unit_length():
    face = NpuFace(bbox=np.zeros(4), kps=np.zeros((5, 2)), det_score=0.9,
                   embedding=np.arange(1, 513, dtype=np.float32))
    assert np.linalg.norm(face.normed_embedding) == pytest.approx(1.0)


def test_model_hash_constants_cover_both_models():
    assert set(nfb.MODEL_SHA256) == set(nfb.MODEL_FILES.values())
    assert all(len(h) == 64 for h in nfb.MODEL_SHA256.values())


# --------------------------------------------------------------------------
# Client / backend failure codes (no hardware)
# --------------------------------------------------------------------------

def test_worker_client_requires_windows_python():
    client = nfb.NpuWorkerClient("", "worker.py")
    with pytest.raises(NpuUnavailable) as e:
        client.start()
    assert e.value.code == "windows_python_not_configured"


def test_worker_client_missing_python_binary(tmp_path):
    client = nfb.NpuWorkerClient(str(tmp_path / "python.exe"), "worker.py")
    with pytest.raises(NpuUnavailable) as e:
        client.start()
    assert e.value.code == "windows_python_missing"


def test_backend_reports_missing_models(tmp_path):
    backend = nfb.NpuFaceBackend(str(tmp_path), windows_python="")
    with pytest.raises(NpuUnavailable) as e:
        backend.initialize()
    assert e.value.code == "model_missing"


# --------------------------------------------------------------------------
# PresenceDetector backend selection / fallback / states
# --------------------------------------------------------------------------

class _Config:
    def __init__(self, presence: dict, storage: str):
        self._data = {"vision.presence": presence, "system.storage_path": storage}

    def get(self, key, default=None):
        return self._data.get(key, default)


def _detector(tmp_path, presence=None, camera=True):
    cfg = _Config(presence or {}, str(tmp_path))
    webcam = MagicMock()
    webcam.device_available = camera
    people = MagicMock()
    people.get_people_with_face_embeddings.return_value = []
    conv = MagicMock()
    conv.conversation_active = False
    return pd.PresenceDetector(cfg, MagicMock(), webcam, people, conv), webcam


def _fake_face():
    return SimpleNamespace(bbox=np.array([0, 0, 100, 100], dtype=np.float32),
                           normed_embedding=np.ones(4, dtype=np.float32) / 2)


class _FakeBackend:
    """Stands in for NpuFaceBackend; behaviour is set per test through class attributes."""
    fail_code = None
    runtime_fail = False
    closed = False

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def initialize(self):
        if self.fail_code:
            raise NpuUnavailable(self.fail_code, "boom")
        return {"execution_devices": {"det": "NPU", "rec": "NPU"}, "npu_name": "Intel(R) AI Boost",
                "openvino": "2026.4.0"}

    def get(self, frame):
        if self.runtime_fail:
            raise NpuUnavailable("worker_exited", "died")
        return [_fake_face()]

    def close(self):
        type(self).closed = True


@pytest.fixture
def fake_backend(monkeypatch):
    _FakeBackend.fail_code = None
    _FakeBackend.runtime_fail = False
    _FakeBackend.closed = False
    monkeypatch.setattr(pd, "NpuFaceBackend", _FakeBackend)
    return _FakeBackend


@pytest.fixture
def cpu_sentinel(monkeypatch):
    cpu = SimpleNamespace(get=lambda frame: [_fake_face()])
    monkeypatch.setattr(pd.PresenceDetector, "_create_cpu_face_app", lambda self: cpu)
    return cpu


def test_default_backend_is_cpu_and_never_touches_npu(tmp_path, fake_backend, cpu_sentinel):
    det, _ = _detector(tmp_path)
    assert det.ensure_backend() == {"requested": "cpu", "active": "cpu", "reason": None}
    assert det._face_app is cpu_sentinel


def test_unknown_backend_value_falls_back_to_cpu(tmp_path, fake_backend, cpu_sentinel):
    det, _ = _detector(tmp_path, {"backend": "tpu"})
    assert det.ensure_backend()["active"] == "cpu"


def test_npu_backend_active_reports_execution_devices(tmp_path, fake_backend, cpu_sentinel):
    det, _ = _detector(tmp_path, {"backend": "npu", "npu": {"windows_python": "C:\\x\\python.exe"}})
    info = det.ensure_backend()
    assert info["active"] == "npu"
    assert info["execution_devices"] == {"det": "NPU", "rec": "NPU"}
    assert det._face_app is not cpu_sentinel
    assert det.get_status()["backend"]["active"] == "npu"


def test_npu_failure_falls_back_to_cpu_with_visible_reason(tmp_path, fake_backend, cpu_sentinel):
    fake_backend.fail_code = "windows_python_not_configured"
    det, _ = _detector(tmp_path, {"backend": "npu"})
    info = det.ensure_backend()
    assert info["active"] == "cpu"
    assert info["reason"] == "windows_python_not_configured"
    assert det.get_status()["backend"]["reason"] == "windows_python_not_configured"


def test_auto_backend_falls_back_to_cpu(tmp_path, fake_backend, cpu_sentinel):
    fake_backend.fail_code = "npu_not_listed"
    det, _ = _detector(tmp_path, {"backend": "auto"})
    assert det.ensure_backend()["active"] == "cpu"


def test_npu_without_fallback_never_uses_cpu(tmp_path, fake_backend, cpu_sentinel):
    fake_backend.fail_code = "interop_unavailable"
    det, _ = _detector(tmp_path, {"backend": "npu", "npu": {"fallback_to_cpu": False}})
    with pytest.raises(NpuUnavailable):
        det.ensure_backend()
    assert det._analyse(np.zeros((10, 10, 3), dtype=np.uint8)) == []
    with pytest.raises(NpuUnavailable):        # sticky until restart, never slips into CPU
        det._get_face_app()
    assert det._face_app is None
    assert det.get_status()["backend"]["active"] is None


def test_runtime_npu_failure_switches_to_cpu_visibly(tmp_path, fake_backend, cpu_sentinel):
    det, _ = _detector(tmp_path, {"backend": "npu"})
    det.ensure_backend()
    fake_backend.runtime_fail = True
    faces = det._analyse(np.zeros((10, 10, 3), dtype=np.uint8))
    assert len(faces) == 1
    assert det._backend_info["active"] == "cpu"
    assert det._backend_info["reason"] == "worker_exited"
    assert fake_backend.closed


def test_status_reports_camera_unavailable_without_fake_frames(tmp_path, fake_backend, cpu_sentinel):
    det, webcam = _detector(tmp_path, {"backend": "npu"}, camera=False)
    assert det.get_status()["camera"] == "UNAVAILABLE"
    assert det._should_skip() is True
    webcam.get_frame.assert_not_called()       # no frame was requested
    assert det._face_app is None               # polling did not touch the backend
    det.ensure_backend()                       # but it is initialisable without a camera
    assert det.get_status()["backend"]["active"] == "npu"
    webcam.device_available = True
    assert det.get_status()["camera"] == "AVAILABLE"


def test_matching_semantics_and_threshold_transparency(tmp_path, fake_backend, cpu_sentinel):
    det, _ = _detector(tmp_path, {"backend": "cpu", "face_confidence_threshold": 0.6,
                                  "min_face_size": 80})
    det._face_cache["p1"] = np.ones(4, dtype=np.float32) / 2   # identical to the fake embedding
    results = det._detect_and_identify(np.zeros((200, 200, 3), dtype=np.uint8))
    assert results == [("p1", pytest.approx(1.0))]
    match = det.last_matches[0]
    assert match["similarity"] == pytest.approx(1.0)
    assert match["threshold"] == 0.6
    assert match["threshold_validated"] is False
    # below threshold -> unknown (None): same semantics as before the change
    det._face_cache["p1"] = np.array([1, -1, 1, -1], dtype=np.float32) / 2
    assert det._detect_and_identify(np.zeros((200, 200, 3), dtype=np.uint8))[0][0] is None
    status = det.get_status()["matching"]
    assert status["threshold"] == 0.6 and status["threshold_validated"] is False


# --------------------------------------------------------------------------
# Real hardware smoke test (skipped unless configured)
# --------------------------------------------------------------------------

def _smoke_env():
    windows_python = os.environ.get("JARVIS_NPU_WINDOWS_PYTHON")
    photos = os.environ.get("JARVIS_NPU_SMOKE_PHOTOS")
    model_dir = os.environ.get("JARVIS_NPU_MODEL_DIR", "/home/alex/jarvis-data/models/insightface/buffalo_l")
    if not (windows_python and photos and Path(photos).is_dir()
            and (Path(model_dir) / nfb.MODEL_FILES["det"]).is_file()):
        return None
    return windows_python, Path(photos), model_dir


@pytest.mark.skipif(_smoke_env() is None, reason="NPU smoke env not configured")
def test_real_npu_smoke():
    import cv2
    windows_python, photos, model_dir = _smoke_env()
    files = sorted(p for p in photos.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    assert files, "no photos"
    backend = nfb.NpuFaceBackend(model_dir, windows_python)
    try:
        info = backend.initialize()
        # Both models really run on the NPU (the worker refuses otherwise)
        assert "NPU" in info["execution_devices"]["det"]
        assert "NPU" in info["execution_devices"]["rec"]
        embeddings = []
        for path in files:
            frame = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
            faces = backend.get(frame)
            assert len(faces) == 1, f"{path.name}: {len(faces)} faces"
            emb = faces[0].normed_embedding
            assert emb.shape == (512,) and np.isfinite(emb).all()
            assert np.linalg.norm(emb) == pytest.approx(1.0, abs=1e-5)
            embeddings.append(emb)
        sims = np.stack(embeddings) @ np.stack(embeddings).T
        assert sims[np.triu_indices(len(files), 1)].min() > 0.5   # measured minimum 0.555 on this set
    finally:
        backend.close()
