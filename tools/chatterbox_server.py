import io
import json
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer

import subprocess
import tempfile
import numpy as np
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

HOST = "127.0.0.1"
PORT = 8765
RATE = 0.89

print("Lade Chatterbox V3...", flush=True)

model = ChatterboxMultilingualTTS.from_pretrained(
    device="cuda",
    t3_model="v3",
)

print(f"READY http://{HOST}:{PORT}", flush=True)


def make_wav(text):
    wav = model.generate(text, language_id="de")
    audio = wav.squeeze().detach().cpu().numpy()

    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav") as src, \
         tempfile.NamedTemporaryFile(suffix=".wav") as dst:

        with wave.open(src.name, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(model.sr)
            f.writeframes(pcm.tobytes())

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-i", src.name,
                "-filter:a", f"atempo={RATE}",
                dst.name,
            ],
            check=True,
        )

        dst.seek(0)
        return dst.read()


class Handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            body = b'{"status":"ok"}'

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404)

    def do_POST(self):
        if self.path != "/tts":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length))
            text = data["text"].strip()

            if not text:
                raise ValueError("Text ist leer")

            wav = make_wav(text)

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav)))
            self.end_headers()
            self.wfile.write(wav)

        except Exception as e:
            body = json.dumps(
                {"error": str(e)}
            ).encode()

            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


HTTPServer((HOST, PORT), Handler).serve_forever()
