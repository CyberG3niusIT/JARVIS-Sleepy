#!/usr/bin/env python3
"""Evaluate the current Sleepy Qwen3-ASR backend on recorded voice-training takes."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import wave
from pathlib import Path

import numpy as np

from core.stt_qwen3 import Qwen3SpeechToText

DEFAULT_ROOT = Path("/home/alex/jarvis-data/voice_training/qwen3-asr-alex")
DEFAULT_MODEL = Path(
    "/home/alex/jarvis-data/models/qwen3-asr/"
    "sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25"
)


class SimpleConfig:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[^\wäöüß]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def edit_distance(ref, hyp):
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i]
        for j, h in enumerate(hyp, start=1):
            cur.append(min(
                cur[-1] + 1,
                prev[j] + 1,
                prev[j - 1] + (r != h),
            ))
        prev = cur
    return prev[-1]


def load_wav(path: Path):
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())
    if width != 2:
        raise RuntimeError(f"Unsupported sample width in {path}: {width}")
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, sr


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL)
    p.add_argument("--hotwords", default="Jarvis")
    args = p.parse_args()

    manifest = args.root / "manifest.jsonl"
    if not manifest.exists():
        raise SystemExit(f"Manifest not found: {manifest}")

    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise SystemExit("Manifest is empty")

    cfg = SimpleConfig({
        "stt.qwen3.model_dir": str(args.model_dir),
        "stt.qwen3.hotwords": args.hotwords,
        "stt.qwen3.num_threads": 6,
        "stt.qwen3.provider": "cpu",
        "stt.qwen3.max_total_len": 512,
        "stt.qwen3.max_new_tokens": 128,
    })

    print(f"Loading current Qwen3-ASR baseline ({args.model_dir.name})...")
    print(f"Hotwords: {args.hotwords!r}\n")
    stt = Qwen3SpeechToText(cfg)

    total_words = 0
    total_errors = 0
    exact = 0

    for row in rows:
        wav = Path(row["audio"])
        audio, sr = load_wav(wav)
        hyp = stt.transcribe(audio, sr)
        ref = row["text"]

        ref_n = normalize_text(ref)
        hyp_n = normalize_text(hyp)
        ref_words = ref_n.split()
        hyp_words = hyp_n.split()
        errors = edit_distance(ref_words, hyp_words)
        wer = errors / max(1, len(ref_words))

        total_words += len(ref_words)
        total_errors += errors
        exact += int(ref_n == hyp_n)

        mark = "OK" if ref_n == hyp_n else "MISS"
        print(f"[{mark}] {row['id']}  WER={wer:.1%}")
        print(f"  SOLL: {ref}")
        print(f"  IST:  {hyp}")

    overall_wer = total_errors / max(1, total_words)
    print("\n" + "=" * 64)
    print(f"Takes:       {len(rows)}")
    print(f"Exakt:       {exact}/{len(rows)} ({exact/len(rows):.1%})")
    print(f"Gesamt-WER:  {overall_wer:.1%}")
    print("=" * 64)


if __name__ == "__main__":
    main()
