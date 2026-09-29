"""Optional Intel-NPU backend for the presence detector (buffalo_l via OpenVINO).

JARVIS runs in WSL2 where the Intel NPU is not reachable (no ``/dev/accel``,
host dxg escape calls are rejected — microsoft/WSL#40445). The inference
therefore runs in a small Windows-side worker (``tools/openvino_npu_worker.py``)
that JARVIS starts through the same WSL->Windows interop the audio bridge uses
(no extra port, no firewall rule, no second control plane).

Split of work:
  * WSL (this module): SCRFD pre/post-processing, alignment via the installed
    ``insightface.utils.face_align`` (the exact code the CPU path uses).
  * Windows worker: compile ``det_10g.onnx`` at [1,3,640,640] and
    ``w600k_r50.onnx`` at [1,3,112,112] on ``NPU`` and run tensors.

Models are never modified. The only graph edit is the in-memory input reshape
to the fixed shapes above. A model that does not end up on ``NPU`` is refused;
there is no silent CPU fallback inside this backend — falling back to the CPU
InsightFace path is a visible decision of ``PresenceDetector``.

The object returned by ``NpuFaceBackend.get(frame)`` mimics the parts of
``insightface.app.common.Face`` that ``PresenceDetector`` uses (``bbox``,
``kps``, ``det_score``, ``embedding``, ``normed_embedding``).
"""

import json
import os
import select
import struct
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from core.logger import get_logger

# Official buffalo_l release (github.com/deepinsight/insightface, model-zoo
# asset buffalo_l.zip, sha256 80ffe37d...ca2f). Files verified 2026-09-25.
MODEL_FILES = {
    "det": "det_10g.onnx",
    "rec": "w600k_r50.onnx",
}
MODEL_SHA256 = {
    "det_10g.onnx": "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91",
    "w600k_r50.onnx": "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43",
}
DET_SHAPE = [1, 3, 640, 640]
REC_SHAPE = [1, 3, 112, 112]
DET_THRESH = 0.5   # InsightFace FaceAnalysis.prepare() default
NMS_THRESH = 0.4   # insightface SCRFD default
FEAT_STRIDES = (8, 16, 32)
NUM_ANCHORS = 2


class NpuUnavailable(RuntimeError):
    """The NPU backend cannot be used. ``code`` is a stable machine-readable reason."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass
class NpuFace:
    bbox: np.ndarray
    kps: np.ndarray
    det_score: float
    embedding: np.ndarray = field(repr=False)

    @property
    def normed_embedding(self) -> np.ndarray:
        return self.embedding / np.linalg.norm(self.embedding)


# --------------------------------------------------------------------------
# SCRFD decoding (mirrors insightface.model_zoo.scrfd.SCRFD.forward/detect)
# --------------------------------------------------------------------------

def _distance2bbox(points, distance):
    return np.stack([points[:, 0] - distance[:, 0], points[:, 1] - distance[:, 1],
                     points[:, 0] + distance[:, 2], points[:, 1] + distance[:, 3]], axis=-1)


def _distance2kps(points, distance):
    preds = []
    for i in range(0, distance.shape[1], 2):
        preds.append(points[:, i % 2] + distance[:, i])
        preds.append(points[:, i % 2 + 1] + distance[:, i + 1])
    return np.stack(preds, axis=-1)


def _nms(dets, thresh):
    x1, y1, x2, y2, scores = (dets[:, i] for i in range(5))
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = np.argsort(-scores, kind="stable")
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1 + 1) * np.maximum(0.0, yy2 - yy1 + 1)
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(ovr <= thresh)[0] + 1]
    return keep


def decode_scrfd(outputs, det_scale, input_size=640, det_thresh=DET_THRESH, nms_thresh=NMS_THRESH):
    """Decode the 9 SCRFD outputs [score x3, bbox x3, kps x3] -> (dets Nx5, kps Nx5x2)."""
    scores_l, boxes_l, kps_l = [], [], []
    for idx, stride in enumerate(FEAT_STRIDES):
        scores = outputs[idx]
        bbox_preds = outputs[idx + 3] * stride
        kps_preds = outputs[idx + 6] * stride
        size = input_size // stride
        centers = np.stack(np.mgrid[:size, :size][::-1], axis=-1).astype(np.float32)
        centers = (centers * stride).reshape(-1, 2)
        centers = np.stack([centers] * NUM_ANCHORS, axis=1).reshape(-1, 2)
        pos = np.where(scores >= det_thresh)[0]
        scores_l.append(scores[pos])
        boxes_l.append(_distance2bbox(centers, bbox_preds)[pos])
        kps_l.append(_distance2kps(centers, kps_preds).reshape(-1, 5, 2)[pos])
    scores = np.vstack(scores_l)
    if scores.size == 0:
        return np.empty((0, 5), dtype=np.float32), np.empty((0, 5, 2), dtype=np.float32)
    order = np.argsort(-scores.ravel(), kind="stable")
    boxes = np.vstack(boxes_l) / det_scale
    kps = np.vstack(kps_l) / det_scale
    pre = np.hstack((boxes, scores)).astype(np.float32, copy=False)[order]
    kps = kps[order]
    keep = _nms(pre, nms_thresh)
    return pre[keep], kps[keep].astype(np.float32, copy=False)


# --------------------------------------------------------------------------
# Windows worker client
# --------------------------------------------------------------------------

def _wslpath(flag: str, path: str) -> str:
    out = subprocess.run(["wslpath", flag, path], capture_output=True, text=True, timeout=10)
    if out.returncode != 0 or not out.stdout.strip():
        raise NpuUnavailable("interop_unavailable", f"wslpath {flag} {path}: {out.stderr.strip()}")
    return out.stdout.strip()


class NpuWorkerClient:
    """Length-prefixed request/response client for ``tools/openvino_npu_worker.py``."""

    def __init__(self, windows_python: str, worker_script: str, timeout: float = 30.0, logger=None):
        self.windows_python = windows_python
        self.worker_script = worker_script
        self.timeout = timeout
        self.logger = logger or get_logger("presence")
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._stderr_tail: deque = deque(maxlen=20)

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        if not self.windows_python:
            raise NpuUnavailable("windows_python_not_configured",
                                 "vision.presence.npu.windows_python / JARVIS_NPU_WINDOWS_PYTHON is empty")
        exe = self.windows_python
        if len(exe) > 1 and exe[1] == ":":  # Windows path -> WSL path
            exe = _wslpath("-u", exe)
        if not os.path.isfile(exe):
            raise NpuUnavailable("windows_python_missing", exe)
        script = _wslpath("-w", self.worker_script)
        try:
            self._proc = subprocess.Popen(
                [exe, "-u", script],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except OSError as e:  # e.g. Exec format error when WSLInterop is not registered
            raise NpuUnavailable("interop_unavailable", f"{type(e).__name__}: {e}") from e
        threading.Thread(target=self._drain_stderr, args=(self._proc,), daemon=True,
                         name="npu-worker-stderr").start()

    def _drain_stderr(self, proc) -> None:
        for line in iter(proc.stderr.readline, b""):
            self._stderr_tail.append(line.decode("utf-8", "replace").rstrip())

    def _read_exact(self, n: int, deadline: float) -> bytes:
        fd = self._proc.stdout.fileno()
        buf = bytearray()
        while len(buf) < n:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
                raise NpuUnavailable("worker_timeout", f"no reply within {self.timeout}s")
            chunk = os.read(fd, n - len(buf))
            if not chunk:
                raise NpuUnavailable("worker_exited", " | ".join(self._stderr_tail)[-500:])
            buf += chunk
        return bytes(buf)

    def request(self, header: dict, body: bytes = b"", timeout: Optional[float] = None):
        with self._lock:
            self.start()
            header = dict(header, body_len=len(body))
            raw = json.dumps(header).encode("utf-8")
            deadline = time.monotonic() + (timeout or self.timeout)
            try:
                self._proc.stdin.write(struct.pack(">I", len(raw)) + raw + body)
                self._proc.stdin.flush()
                head_len = struct.unpack(">I", self._read_exact(4, deadline))[0]
                reply = json.loads(self._read_exact(head_len, deadline).decode("utf-8"))
                n_body = int(reply.get("body_len", 0))
                reply_body = self._read_exact(n_body, deadline) if n_body else b""
            except NpuUnavailable:
                self.close(kill=True)
                raise
            except (BrokenPipeError, OSError, ValueError) as e:
                self.close(kill=True)
                raise NpuUnavailable("worker_protocol_error", f"{type(e).__name__}: {e}") from e
        if not reply.get("ok"):
            raise NpuUnavailable(reply.get("error_code", "worker_error"), reply.get("error", ""))
        return reply, reply_body

    def close(self, kill: bool = False) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if not kill and proc.poll() is None:
                raw = json.dumps({"cmd": "shutdown", "body_len": 0}).encode("utf-8")
                proc.stdin.write(struct.pack(">I", len(raw)) + raw)
                proc.stdin.flush()
                proc.wait(timeout=3)
        except Exception:
            pass
        finally:
            if proc.poll() is None:
                proc.kill()
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    stream.close()
                except Exception:
                    pass


# --------------------------------------------------------------------------
# Backend
# --------------------------------------------------------------------------

class NpuFaceBackend:
    """SCRFD detection + ArcFace embedding on the Intel NPU (via the Windows worker)."""

    def __init__(self, model_dir: str, windows_python: str, worker_script: Optional[str] = None,
                 timeout: float = 30.0, logger=None):
        self.logger = logger or get_logger("presence")
        self.model_dir = Path(model_dir)
        if worker_script is None:
            worker_script = str(Path(__file__).resolve().parent.parent / "tools" / "openvino_npu_worker.py")
        self._client = NpuWorkerClient(windows_python, worker_script, timeout, self.logger)
        self.info: dict = {"backend": "npu", "initialized": False}

    def initialize(self) -> dict:
        """Start the worker, verify the NPU is listed, compile both models. Idempotent."""
        if self.info.get("initialized"):
            return self.info
        for filename in MODEL_FILES.values():
            if not (self.model_dir / filename).is_file():
                raise NpuUnavailable("model_missing", str(self.model_dir / filename))
        try:
            import cv2  # noqa: F401
            from insightface.utils import face_align  # noqa: F401
        except ImportError as e:
            raise NpuUnavailable("insightface_missing", str(e)) from e

        hello, _ = self._client.request({"cmd": "hello"})
        if "NPU" not in hello.get("devices", []):
            self._client.close()
            raise NpuUnavailable("npu_not_listed", f"OpenVINO devices: {hello.get('devices')}")
        info = {"backend": "npu", "openvino": hello.get("openvino"), "npu_name": hello.get("npu_name"),
                "execution_devices": {}}
        for name, shape in (("det", DET_SHAPE), ("rec", REC_SHAPE)):
            filename = MODEL_FILES[name]
            try:
                reply, _ = self._client.request({
                    "cmd": "load", "name": name, "path": _wslpath("-w", str(self.model_dir / filename)),
                    "input_shape": shape, "device": "NPU",
                    "expected_sha256": MODEL_SHA256[filename],
                }, timeout=180)  # first NPU compile can take a while
            except NpuUnavailable:
                self._client.close()
                raise
            info["execution_devices"][name] = reply["execution_devices"]
        info["initialized"] = True
        self.info = info
        self.logger.info("NPU face backend ready: %s", info)
        return info

    # -- helpers -----------------------------------------------------------

    def _infer(self, name: str, blob: np.ndarray) -> list:
        blob = np.ascontiguousarray(blob, dtype=np.float32)
        reply, body = self._client.request({"cmd": "infer", "name": name, "dtype": "float32",
                                            "shape": list(blob.shape)}, blob.tobytes())
        outs, offset = [], 0
        for spec in reply["outputs"]:
            count = int(np.prod(spec["shape"]))
            outs.append(np.frombuffer(body, dtype=spec["dtype"], count=count,
                                      offset=offset).reshape(spec["shape"]))
            offset += count * np.dtype(spec["dtype"]).itemsize
        return outs

    def get(self, frame_bgr: np.ndarray) -> list:
        """Detect + embed all faces in a BGR frame (same contract as FaceAnalysis.get)."""
        import cv2
        from insightface.utils import face_align

        self.initialize()
        h, w = frame_bgr.shape[:2]
        size = DET_SHAPE[2]
        im_ratio = float(h) / w
        if im_ratio > 1.0:
            new_h, new_w = size, int(size / im_ratio)
        else:
            new_w, new_h = size, int(size * im_ratio)
        det_scale = float(new_h) / h
        canvas = np.zeros((size, size, 3), dtype=np.uint8)
        canvas[:new_h, :new_w, :] = cv2.resize(frame_bgr, (new_w, new_h))
        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 128.0, (size, size), (127.5, 127.5, 127.5), swapRB=True)
        dets, kpss = decode_scrfd(self._infer("det", blob), det_scale, size)

        faces = []
        for det, kps in zip(dets, kpss):
            aimg = face_align.norm_crop(frame_bgr, landmark=kps, image_size=REC_SHAPE[2])
            rblob = cv2.dnn.blobFromImages([aimg], 1.0 / 127.5, (REC_SHAPE[3], REC_SHAPE[2]),
                                           (127.5, 127.5, 127.5), swapRB=True)
            emb = self._infer("rec", rblob)[0].reshape(-1)
            faces.append(NpuFace(bbox=det[:4].astype(np.float32), kps=kps,
                                 det_score=float(det[4]), embedding=emb))
        return faces

    def close(self) -> None:
        self._client.close()
        self.info = {"backend": "npu", "initialized": False}
