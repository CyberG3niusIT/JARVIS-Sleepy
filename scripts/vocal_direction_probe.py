#!/usr/bin/env python3
"""Write A/B WAVs from the live Chatterbox server for a listening test.

The probe does not play audio or change server parameters. Its silence values
are provisional and should only be accepted after listening on Sleepy.
"""

from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.vocal_directions import PcmChunk, compose_directed_pcm, parse_directions


BASE_TEXT = "Die Prüfung ist abgeschlossen, Alex. Ich beginne jetzt."
COMMA_TEXT = "Der Status ist gut, Alex, und alle Systeme laufen."


def request_audio(endpoint: str, text: str) -> PcmChunk:
    import json

    body = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        endpoint, data=body, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        wav_data = response.read()
    with wave.open(io.BytesIO(wav_data), "rb") as source:
        chunk = PcmChunk(
            source.readframes(source.getnframes()),
            source.getframerate(),
            source.getnchannels(),
            source.getsampwidth(),
            "pcm_s16le" if source.getcomptype() == "NONE" else source.getcomptype(),
        )
    if (chunk.channels, chunk.sample_width, chunk.encoding) != (1, 2, "pcm_s16le"):
        raise ValueError("Chatterbox returned unsupported WAV format")
    return chunk


def write_wav(path: Path, chunk: PcmChunk) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(chunk.channels)
        output.setsampwidth(chunk.sample_width)
        output.setframerate(chunk.sample_rate)
        output.writeframes(chunk.data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8765/tts")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    baseline = request_audio(args.endpoint, BASE_TEXT)
    write_wav(args.output_dir / "00_baseline.wav", baseline)
    write_wav(args.output_dir / "01_natural_commas.wav", request_audio(args.endpoint, COMMA_TEXT))

    for index, kind in enumerate(("short", "medium", "long"), start=2):
        directed = BASE_TEXT.replace(
            "Alex. Ich", f"Alex.[voice:pause={kind}] Ich",
        )
        plan = parse_directions(directed)
        pcm, rate = compose_directed_pcm(
            plan,
            lambda segment: request_audio(args.endpoint, segment.strip()),
            str.strip,
        )
        if pcm is None or rate is None:
            raise RuntimeError("Directed probe synthesis failed")
        write_wav(args.output_dir / f"{index:02d}_pause_{kind}.wav", PcmChunk(pcm, rate))

    print(args.output_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
