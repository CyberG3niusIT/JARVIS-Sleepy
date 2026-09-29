"""
Qwen3-ASR backend for JARVIS.

Uses sherpa-onnx OfflineRecognizer with a persistent recognizer.
The model is loaded once when JARVIS starts.

Whisper remains available as fallback through core/stt.py.
"""

import time
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.signal import resample_poly

from core.logger import get_logger


class Qwen3SpeechToText:
    """Qwen3-ASR speech recognition through sherpa-onnx."""

    def __init__(self, config):
        self.config = config
        self.logger = get_logger(__name__, config)

        self.model_dir = Path(
            config.get(
                "stt.qwen3.model_dir",
                "/home/alex/jarvis-data/models/qwen3-asr/"
                "sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25",
            )
        )

        self.hotwords = config.get(
            "stt.qwen3.hotwords",
            "Jarvis,Hey Jarvis",
        )

        self.num_threads = int(
            config.get("stt.qwen3.num_threads", 6)
        )

        self.provider = config.get(
            "stt.qwen3.provider",
            "cpu",
        )

        self.max_new_tokens = int(
            config.get("stt.qwen3.max_new_tokens", 128)
        )

        self.max_total_len = int(
            config.get("stt.qwen3.max_total_len", 512)
        )

        self.sample_rate = 16000

        self.conv_frontend = (
            self.model_dir / "conv_frontend.onnx"
        )
        self.encoder = (
            self.model_dir / "encoder.int8.onnx"
        )
        self.decoder = (
            self.model_dir / "decoder.int8.onnx"
        )
        self.tokenizer = (
            self.model_dir / "tokenizer"
        )

        required = [
            self.conv_frontend,
            self.encoder,
            self.decoder,
            self.tokenizer,
        ]

        missing = [
            str(p) for p in required
            if not p.exists()
        ]

        if missing:
            raise FileNotFoundError(
                "Qwen3-ASR model incomplete. Missing: "
                + ", ".join(missing)
            )

        try:
            import sherpa_onnx
        except ImportError as e:
            raise ImportError(
                "sherpa-onnx is not installed in the JARVIS venv"
            ) from e

        self.logger.info(
            "Loading Qwen3-ASR from %s",
            self.model_dir,
        )

        self.logger.info(
            "Qwen3-ASR hotwords: %s",
            self.hotwords,
        )

        self.recognizer = (
            sherpa_onnx.OfflineRecognizer.from_qwen3_asr(
                conv_frontend=str(self.conv_frontend),
                encoder=str(self.encoder),
                decoder=str(self.decoder),
                tokenizer=str(self.tokenizer),
                hotwords=self.hotwords,
                num_threads=self.num_threads,
                sample_rate=self.sample_rate,
                feature_dim=128,
                provider=self.provider,
                max_total_len=self.max_total_len,
                max_new_tokens=self.max_new_tokens,
                temperature=1e-6,
                top_p=0.8,
                seed=42,
            )
        )

        self.logger.info(
            "Qwen3-ASR ready "
            "(provider=%s, threads=%d)",
            self.provider,
            self.num_threads,
        )

    def _prepare_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
    ) -> np.ndarray:
        """Convert incoming audio to mono float32 16 kHz."""

        audio = np.asarray(audio_data)

        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        if audio.dtype != np.float32:
            if np.issubdtype(audio.dtype, np.integer):
                max_val = float(
                    np.iinfo(audio.dtype).max
                )
                audio = (
                    audio.astype(np.float32)
                    / max_val
                )
            else:
                audio = audio.astype(np.float32)

        if sample_rate != self.sample_rate:
            from math import gcd

            g = gcd(
                int(sample_rate),
                self.sample_rate,
            )

            audio = resample_poly(
                audio,
                self.sample_rate // g,
                int(sample_rate) // g,
            ).astype(np.float32)

        audio = np.nan_to_num(
            audio,
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )

        audio = np.clip(
            audio,
            -1.0,
            1.0,
        ).astype(np.float32)

        return audio

    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        speaker_user_id: Optional[str] = None,
    ) -> str:
        """
        Transcribe one complete utterance.

        speaker_user_id is accepted for API compatibility with
        the existing Whisper STT backend.
        """

        started = time.monotonic()
        audio_duration_s = len(audio_data) / sample_rate if sample_rate else 0.0
        try:
            audio = self._prepare_audio(
                audio_data,
                sample_rate,
            )

            if len(audio) < 1600:
                self._emit_transcription_event(
                    status="empty",
                    text_length=0,
                    audio_duration_s=audio_duration_s,
                    latency_ms=(time.monotonic() - started) * 1000,
                )
                return ""

            stream = self.recognizer.create_stream()

            stream.accept_waveform(
                self.sample_rate,
                audio,
            )

            self.recognizer.decode_stream(
                stream
            )

            result = stream.result
            text = (
                result.text.strip()
                if result is not None
                else ""
            )

            # Speech content is private; retain only a length-based diagnostic.
            self.logger.info("Qwen3-ASR transcription completed (text_len=%d)", len(text))
            self._emit_transcription_event(
                status="success" if text else "empty",
                text_length=len(text),
                audio_duration_s=audio_duration_s,
                latency_ms=(time.monotonic() - started) * 1000,
            )

            return text

        except Exception as e:
            self._emit_transcription_event(
                status="error",
                text_length=0,
                audio_duration_s=audio_duration_s,
                latency_ms=(time.monotonic() - started) * 1000,
                error_type=type(e).__name__,
            )
            self.logger.error(
                "Qwen3-ASR transcription failed: %s",
                e,
                exc_info=True,
            )
            return ""

    @staticmethod
    def _emit_transcription_event(
        *, status: str, text_length: int, audio_duration_s: float, latency_ms: float,
        error_type: Optional[str] = None,
    ) -> None:
        """Emit content-free Qwen3 usage metrics without affecting transcription."""
        try:
            from core.event_logger import get_event_logger

            event_logger = get_event_logger()
            if event_logger:
                event_logger.emit(
                    category="inference",
                    event="stt_transcription",
                    message=f"Qwen3-ASR {status}: {text_length} chars in {latency_ms:.0f}ms",
                    severity=(
                        "error"
                        if status == "error"
                        else "info"
                        if status == "success"
                        else "debug"
                    ),
                    source="stt",
                    stage="stt",
                    status=status,
                    latency_ms=round(latency_ms, 1),
                    duration_ms=round(latency_ms, 1),
                    model="qwen3-asr",
                    metadata={
                        "engine": "qwen3-asr",
                        "text_length": text_length,
                        "audio_duration_s": round(audio_duration_s, 2),
                        "stt_latency_ms": round(latency_ms, 1),
                        **({"error_type": error_type} if error_type else {}),
                    },
                )
        except Exception:
            pass  # Observability must never break STT.
