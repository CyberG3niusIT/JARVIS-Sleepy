#!/usr/bin/env python3
"""Differential JARVIS voice probe for real Sleepy hardware.

Stages isolate the exact layer that changes pronunciation:
  A: raw text -> Chatterbox HTTP -> Windows audio
  B: GermanTTSNormalizer -> Chatterbox HTTP -> Windows audio
  C: TextToSpeech.speak(normalize=True) -> Windows audio
  D: SpeechChunker -> StreamingAudioPipeline -> Windows audio

Piper fallback is deliberately disabled inside this diagnostic so a failed
Chatterbox stage cannot be mistaken for a pronunciation change.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config import Config
from core.logger import get_logger
from core.pipeline import StreamingAudioPipeline
from core.speech_chunker import SpeechChunker
from core.tts import TextToSpeech

DEFAULT_TEXT = (
    "Jarvis, WSL zwei läuft unter Windows elf und Ubuntu vierundzwanzig null vier "
    "wird für den lokalen Backend Stack verwendet."
)


def _direct_wav(tts: TextToSpeech, text: str) -> bytes:
    response = tts._chatterbox_session.post(
        tts.chatterbox_endpoint,
        json={"text": text},
        timeout=(tts.chatterbox_connect_timeout, tts.chatterbox_timeout),
    )
    response.raise_for_status()
    wav = response.content
    if not wav.startswith(b"RIFF"):
        raise RuntimeError("Chatterbox returned invalid WAV data")
    return wav


def _require_windows(tts: TextToSpeech) -> None:
    if tts.output_backend != "windows":
        raise RuntimeError(
            f"Dieser Probe-Lauf erwartet audio.output_backend=windows, ist {tts.output_backend!r}"
        )


def _chunks(text: str) -> list[str]:
    chunker = SpeechChunker()
    result: list[str] = []
    for token in text.split(" "):
        chunk = chunker.feed(token + " ")
        if chunk:
            result.append(chunk)
    tail = chunker.flush()
    if tail:
        result.append(tail)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("A", "B", "C", "D"))
    parser.add_argument("--text", default=DEFAULT_TEXT)
    args = parser.parse_args(argv)

    config = Config()
    tts = TextToSpeech(config)
    _require_windows(tts)

    # Diagnostic invariant: never let Piper contaminate an A/B/C/D comparison.
    tts._fallback_to_piper = lambda text: False
    tts._piper_generate_pcm = lambda text: (None, None)

    raw = args.text
    normalized = tts.normalizer.normalize(raw) if tts.normalizer else raw

    print(f"STAGE {args.stage}")
    print(f"RAW:        {raw}")
    print(f"NORMALIZED: {normalized}")

    if args.stage == "A":
        wav = _direct_wav(tts, raw)
        ok = tts._play_wav_windows(wav)
    elif args.stage == "B":
        wav = _direct_wav(tts, normalized)
        ok = tts._play_wav_windows(wav)
    elif args.stage == "C":
        ok = tts.speak(raw, normalize=True)
    else:
        chunks = _chunks(raw)
        print("CHUNKS:")
        for i, chunk in enumerate(chunks, 1):
            print(f"  {i}: {chunk}")
        pipeline = StreamingAudioPipeline(
            tts,
            logger=get_logger("voice_abcd_probe", config),
        )
        pipeline.start()
        for chunk in chunks:
            pipeline.put(chunk)
        pipeline.finish()
        ok = pipeline._error is None

    print(f"RESULT: {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
