#!/usr/bin/env python3
"""Interactive voice-data collector for Sleepy JARVIS / Qwen3-ASR.

Records only when the user explicitly starts a take. No ambient or background
conversations are captured. Audio is stored outside the git repository under
/home/alex/jarvis-data by default.
"""

from __future__ import annotations

import argparse
import json
import math
import queue
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly

TARGET_SR = 16000
DEFAULT_ROOT = Path("/home/alex/jarvis-data/voice_training/qwen3-asr-alex")
DEFAULT_PROMPTS = Path(__file__).resolve().parents[1] / "voice_training" / "prompts_de.txt"


def parse_args():
    p = argparse.ArgumentParser(description="Collect explicit voice-training takes for Qwen3-ASR")
    p.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    p.add_argument("--device", default="pulse")
    p.add_argument("--limit", type=int, default=0, help="Max new takes this run, 0 = unlimited")
    p.add_argument("--review", action="store_true", help="Ask to keep/redraw each take")
    p.add_argument("--rebuild", action="store_true", help="Only rebuild train/eval JSONL from manifest")
    return p.parse_args()


def load_prompts(path: Path):
    if not path.exists():
        raise SystemExit(f"Prompt file not found: {path}")
    prompts = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        prompts.append(line)
    if not prompts:
        raise SystemExit("Prompt file is empty")
    return prompts


def read_manifest(path: Path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_manifest(path: Path, rows):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def build_splits(root: Path, rows):
    train_path = root / "train.jsonl"
    eval_path = root / "eval.jsonl"
    train, eval_ = [], []
    for idx, row in enumerate(rows, start=1):
        item = {
            "audio": row["audio"],
            "text": f"language German<asr_text>{row['text']}",
        }
        # Deterministic ~15% holdout. These files are never used for training.
        (eval_ if idx % 7 == 0 else train).append(item)

    for path, data in ((train_path, train), (eval_path, eval_)):
        with path.open("w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return len(train), len(eval_)


def resolve_device(device_name: str):
    try:
        info = sd.query_devices(device_name, "input")
        return device_name, float(info["default_samplerate"])
    except Exception:
        # Fall back to default input device if 'pulse' cannot be resolved by name.
        info = sd.query_devices(kind="input")
        return None, float(info["default_samplerate"])


def record_take(device, device_sr: float):
    chunks = []
    errors = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            errors.put(str(status))
        audio = indata[:, 0] if indata.ndim > 1 else indata
        chunks.append(np.asarray(audio, dtype=np.float32).copy())

    input("  ENTER = Aufnahme starten")
    print("  🔴 Aufnahme läuft. Normal sprechen. ENTER = stoppen")

    with sd.InputStream(
        device=device,
        channels=1,
        samplerate=device_sr,
        dtype="float32",
        callback=callback,
    ):
        input()

    if not chunks:
        return np.array([], dtype=np.float32), []

    audio = np.concatenate(chunks)
    warnings = []
    while not errors.empty():
        warnings.append(errors.get())

    src_sr = int(round(device_sr))
    if src_sr != TARGET_SR:
        g = math.gcd(src_sr, TARGET_SR)
        audio = resample_poly(audio, TARGET_SR // g, src_sr // g).astype(np.float32)

    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    audio = np.clip(audio, -1.0, 1.0)
    return audio, warnings


def save_wav(path: Path, audio: np.ndarray):
    pcm = (audio * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(TARGET_SR)
        wf.writeframes(pcm.tobytes())


def audio_stats(audio: np.ndarray):
    if len(audio) == 0:
        return 0.0, -120.0, 0.0
    duration = len(audio) / TARGET_SR
    rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
    rms_db = 20.0 * math.log10(max(rms, 1e-6))
    peak = float(np.max(np.abs(audio)))
    return duration, rms_db, peak


def main():
    args = parse_args()
    root = args.root.expanduser().resolve()
    wav_dir = root / "wav"
    manifest_path = root / "manifest.jsonl"
    root.mkdir(parents=True, exist_ok=True)
    wav_dir.mkdir(parents=True, exist_ok=True)

    rows = read_manifest(manifest_path)
    if args.rebuild:
        train_n, eval_n = build_splits(root, rows)
        print(f"Dataset rebuilt: train={train_n}, eval={eval_n}")
        return

    prompts = load_prompts(args.prompts)
    completed_ids = {row["id"] for row in rows}
    device, device_sr = resolve_device(args.device)

    print("=" * 72)
    print("SLEEPY JARVIS - QWEN3-ASR VOICE TRAINING")
    print("=" * 72)
    print("Es wird ausschließlich aufgenommen, wenn du ENTER drückst.")
    print("Keine Hintergrundgespräche, Telefonate oder Ambient-Aufzeichnung.")
    print(f"Mikrofon: {args.device if device is not None else 'default'} @ {device_sr:.0f} Hz")
    print(f"Ziel:      16 kHz Mono WAV")
    print(f"Datensatz: {root}")
    print()

    new_count = 0
    for index, text in enumerate(prompts, start=1):
        utt_id = f"utt_{index:04d}"
        if utt_id in completed_ids:
            continue
        if args.limit and new_count >= args.limit:
            break

        while True:
            print(f"\n[{index}/{len(prompts)}] {text}")
            action = input("ENTER=aufnehmen | s=überspringen | q=beenden: ").strip().lower()
            if action == "q":
                train_n, eval_n = build_splits(root, rows)
                print(f"\nGespeichert. train={train_n}, eval={eval_n}")
                return
            if action == "s":
                break
            if action:
                continue

            audio, warnings = record_take(device, device_sr)
            duration, rms_db, peak = audio_stats(audio)
            print(f"  Dauer {duration:.2f}s | RMS {rms_db:.1f} dBFS | Peak {peak:.3f}")
            for warning in warnings:
                print(f"  ⚠ Audio: {warning}")

            if duration < 0.35:
                print("  ❌ Zu kurz, bitte neu aufnehmen.")
                continue
            if peak < 0.01:
                print("  ❌ Signal zu leise, bitte neu aufnehmen.")
                continue
            if peak >= 0.999:
                print("  ⚠ Möglicherweise Clipping.")

            keep = ""
            if args.review:
                keep = input("ENTER=behalten | r=neu | s=verwerfen | q=beenden: ").strip().lower()
            if keep == "q":
                train_n, eval_n = build_splits(root, rows)
                print(f"\nGespeichert. train={train_n}, eval={eval_n}")
                return
            if keep == "r":
                continue
            if keep == "s":
                break

            wav_path = wav_dir / f"{utt_id}.wav"
            save_wav(wav_path, audio)
            row = {
                "id": utt_id,
                "audio": str(wav_path),
                "text": text,
                "duration_s": round(duration, 3),
                "rms_dbfs": round(rms_db, 2),
                "peak": round(peak, 5),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            rows.append(row)
            write_manifest(manifest_path, rows)
            completed_ids.add(utt_id)
            new_count += 1
            print("  ✅ gespeichert")
            break

    train_n, eval_n = build_splits(root, rows)
    print("\nFertig.")
    print(f"Aufnahmen gesamt: {len(rows)}")
    print(f"Train: {train_n}")
    print(f"Eval:  {eval_n}")
    print(f"Pfad:  {root}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAbgebrochen. Bereits gespeicherte Takes bleiben erhalten.")
        sys.exit(130)
