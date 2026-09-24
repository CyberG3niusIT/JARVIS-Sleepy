"""Chatterbox Multilingual V3 TTS server.

Minimal local HTTP wrapper around ChatterboxMultilingualTTS. Runs single-
threaded on purpose: the model lives on one GPU and can't safely serve two
generate() calls at once, so http.server's default one-request-at-a-time
handling is exactly right here — no ThreadingHTTPServer, no request queue.

Generation parameters (verified signature):
    generate(text, language_id, audio_prompt_path=None, exaggeration=0.5,
             cfg_weight=0.5, temperature=0.8, repetition_penalty=1.2,
             min_p=0.05, top_p=1.0)

Defaults come from CHATTERBOX_* env vars so they can be tuned without
touching this file, and can be overridden per-request via the JSON body.
The production values live in systemd/chatterbox.env.
"""

import hashlib
import io
import json
import os
import subprocess
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np

HOST = "127.0.0.1"
PORT = int(os.environ.get("CHATTERBOX_PORT", "8765"))

# Playback tempo applied after generation via ffmpeg atempo. 0.89 was tuned
# by ear for natural German pacing at the current model/voice.
TEMPO = float(os.environ.get("CHATTERBOX_TEMPO", "0.89"))
LANGUAGE_ID = os.environ.get("CHATTERBOX_LANGUAGE", "de")

DEFAULT_GEN_PARAMS = {
    "exaggeration": float(os.environ.get("CHATTERBOX_EXAGGERATION", "0.5")),
    "cfg_weight": float(os.environ.get("CHATTERBOX_CFG_WEIGHT", "0.5")),
    "temperature": float(os.environ.get("CHATTERBOX_TEMPERATURE", "0.8")),
    "repetition_penalty": float(os.environ.get("CHATTERBOX_REPETITION_PENALTY", "1.2")),
    "min_p": float(os.environ.get("CHATTERBOX_MIN_P", "0.05")),
    "top_p": float(os.environ.get("CHATTERBOX_TOP_P", "1.0")),
}
AUDIO_PROMPT_PATH = os.environ.get("CHATTERBOX_AUDIO_PROMPT_PATH") or None

# Set in main() after the HTTP socket has been bound successfully.
model = None


def _file_sha256(path: str | None) -> str | None:
    """Return a file SHA256 without loading the whole reference WAV into RAM."""
    if not path:
        return None
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


AUDIO_PROMPT_SHA256 = _file_sha256(AUDIO_PROMPT_PATH)


def _apply_tempo(pcm_bytes: bytes, tempo: float, sample_rate: int) -> bytes:
    """Resample playback speed via ffmpeg, piping raw PCM through stdin/stdout."""
    if tempo == 1.0:
        return pcm_bytes

    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "s16le", "-ac", "1", "-ar", str(sample_rate),
            "-i", "pipe:0",
            "-filter:a", f"atempo={tempo}",
            "-f", "s16le", "-ac", "1", "-ar", str(sample_rate),
            "pipe:1",
        ],
        input=pcm_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout


def make_wav(text: str, gen_params: dict) -> bytes:
    if model is None:
        raise RuntimeError("Chatterbox model is not initialized")

    wav = model.generate(
        text,
        language_id=LANGUAGE_ID,
        audio_prompt_path=AUDIO_PROMPT_PATH,
        **gen_params,
    )
    audio = wav.squeeze().detach().cpu().numpy()

    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767).astype(np.int16).tobytes()
    pcm = _apply_tempo(pcm, TEMPO, model.sr)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(model.sr)
        f.writeframes(pcm)

    return buf.getvalue()


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

        if self.path == "/config":
            body = json.dumps({
                "language": LANGUAGE_ID,
                "tempo": TEMPO,
                "audio_prompt_path": AUDIO_PROMPT_PATH,
                "audio_prompt_sha256": AUDIO_PROMPT_SHA256,
                **DEFAULT_GEN_PARAMS,
            }).encode()

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

            gen_params = dict(DEFAULT_GEN_PARAMS)
            for key in gen_params:
                if key in data:
                    gen_params[key] = float(data[key])

            wav = make_wav(text, gen_params)

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav)))
            self.end_headers()
            self.wfile.write(wav)

        except Exception as e:
            body = json.dumps({"error": str(e)}).encode()

            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def main() -> None:
    """Bind first, load the GPU model second, announce READY last.

    Binding before model load prevents a second Chatterbox process from spending
    GPU time loading the model only to discover that port 8765 is already used.
    READY is emitted only after both the socket bind and model initialization
    have succeeded.
    """
    global model

    # HTTPServer binds/activates the socket in its constructor but does not
    # accept requests until serve_forever() is entered below.
    server = HTTPServer((HOST, PORT), Handler)

    try:
        print("Lade Chatterbox V3...", flush=True)
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        model = ChatterboxMultilingualTTS.from_pretrained(
            device="cuda",
            t3_model="v3",
        )

        print(
            f"READY http://{HOST}:{PORT} (tempo={TEMPO}, lang={LANGUAGE_ID})",
            flush=True,
        )
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
