"""OpenVINO NPU tensor worker (Windows side).

Runs under a *Windows* Python that has ``numpy`` and ``openvino`` (no OpenCV,
no JARVIS imports). JARVIS runs in WSL2, where the Intel NPU is not reachable
(no ``/dev/accel``; dxg escape calls are rejected by the host), so
``core/npu_face_backend.py`` launches this script through the same WSL->Windows
interop the audio bridge uses and talks to it over stdin/stdout.

The worker is deliberately dumb: it compiles a model on a named device and runs
tensors. All image pre/post-processing stays in JARVIS. It never modifies a
model file; the only graph edit is the in-memory input reshape to a fixed shape.

Protocol (both directions): ``uint32 big-endian header_len`` + JSON header +
``header["body_len"]`` raw bytes. Requests carry ``cmd``; replies carry ``ok``.

  hello                                   -> versions, available devices
  load  name path input_shape device      -> compile; reply carries the real
        [expected_sha256]                    EXECUTION_DEVICES
  infer name dtype shape (+ body)         -> outputs (+ body)
  shutdown

A model requested on ``NPU`` whose EXECUTION_DEVICES does not contain ``NPU`` is
refused (``device_mismatch``) instead of being reported as success.
"""

import hashlib
import json
import os
import struct
import sys
import time

_OUT = sys.stdout.buffer
_IN = sys.stdin.buffer
sys.stdout = sys.stderr  # stray prints must never corrupt the protocol stream

if sys.platform == "win32":
    import msvcrt

    msvcrt.setmode(0, os.O_BINARY)
    msvcrt.setmode(1, os.O_BINARY)


def _read_exact(n):
    buf = bytearray()
    while len(buf) < n:
        chunk = _IN.read(n - len(buf))
        if not chunk:
            raise EOFError
        buf += chunk
    return bytes(buf)


def _recv():
    header_len = struct.unpack(">I", _read_exact(4))[0]
    header = json.loads(_read_exact(header_len).decode("utf-8"))
    body = _read_exact(int(header["body_len"])) if header.get("body_len") else b""
    return header, body


def _send(header, body=b""):
    header = dict(header)
    header["body_len"] = len(body)
    raw = json.dumps(header).encode("utf-8")
    _OUT.write(struct.pack(">I", len(raw)) + raw + body)
    _OUT.flush()


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    import numpy as np
    import openvino as ov

    core = ov.Core()
    compiled = {}

    while True:
        try:
            req, body = _recv()
        except EOFError:
            return 0
        cmd = req.get("cmd")
        try:
            if cmd == "hello":
                devices = list(core.available_devices)
                npu_name = None
                if "NPU" in devices:
                    npu_name = str(core.get_property("NPU", "FULL_DEVICE_NAME"))
                _send({"ok": True, "openvino": ov.__version__, "devices": devices,
                       "npu_name": npu_name, "python": sys.version.split()[0]})
            elif cmd == "load":
                path, device = req["path"], req["device"]
                expected = req.get("expected_sha256")
                if expected:
                    actual = _sha256(path)
                    if actual.lower() != expected.lower():
                        _send({"ok": False, "error_code": "model_hash_mismatch",
                               "error": f"{path}: sha256 {actual} != expected {expected}"})
                        continue
                if device not in core.available_devices:
                    _send({"ok": False, "error_code": "device_missing",
                           "error": f"{device} not in {list(core.available_devices)}"})
                    continue
                model = core.read_model(path)
                model.reshape({model.inputs[0].get_any_name(): list(req["input_shape"])})
                if model.is_dynamic():
                    _send({"ok": False, "error_code": "model_dynamic",
                           "error": "model still dynamic after input reshape"})
                    continue
                t0 = time.perf_counter()
                cm = core.compile_model(model, device)
                compile_s = time.perf_counter() - t0
                devices = str(cm.get_property("EXECUTION_DEVICES"))
                if device == "NPU" and "NPU" not in devices:
                    _send({"ok": False, "error_code": "device_mismatch",
                           "error": f"requested NPU, EXECUTION_DEVICES={devices}"})
                    continue
                compiled[req["name"]] = cm
                _send({"ok": True, "execution_devices": devices, "compile_seconds": round(compile_s, 2),
                       "outputs": [{"shape": [int(d) for d in o.get_shape()],
                                    "dtype": str(o.get_element_type())} for o in cm.outputs]})
            elif cmd == "infer":
                cm = compiled.get(req["name"])
                if cm is None:
                    _send({"ok": False, "error_code": "not_loaded", "error": str(req.get("name"))})
                    continue
                arr = np.frombuffer(body, dtype=req["dtype"]).reshape(req["shape"])
                res = cm.create_infer_request().infer({0: arr})
                outs = [np.ascontiguousarray(np.array(res[o])) for o in cm.outputs]
                _send({"ok": True,
                       "outputs": [{"shape": list(o.shape), "dtype": str(o.dtype)} for o in outs]},
                      b"".join(o.tobytes() for o in outs))
            elif cmd == "shutdown":
                _send({"ok": True})
                return 0
            else:
                _send({"ok": False, "error_code": "bad_command", "error": str(cmd)})
        except Exception as e:  # report, keep serving
            _send({"ok": False, "error_code": type(e).__name__, "error": str(e)[:2000]})


if __name__ == "__main__":
    sys.exit(main())
