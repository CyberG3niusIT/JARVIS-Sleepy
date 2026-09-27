"""
Text-to-Speech Engine

Multi-engine TTS: Chatterbox Multilingual V3 (primary, GPU service),
Kokoro (in-process, CPU) and Piper (subprocess fallback).
Configured via tts.engine in config.yaml.
"""

import subprocess
import json
import os
import io
import wave
import time
import random
import threading
from pathlib import Path
from typing import Optional, Dict

from core.logger import get_logger
from core.tts_normalizer_de import get_normalizer
from core.vocal_directions import (
    PcmChunk, compose_directed_pcm, has_directions, log_diagnostics,
    parse_directions, resample_pcm_s16le,
)

logger = get_logger(__name__)


def resolve_output_device(configured: str) -> str:
    """Resolve audio output device name to ALSA device string.

    If configured value is already an ALSA string (plughw:, hw:, default),
    use it directly. Otherwise, search /proc/asound/cards by name and
    return plughw:N,0 for the matching card that has playback capability.
    """
    if not configured or configured == "default":
        return "default"

    if configured in ("pulse", "pipewire"):
        return configured

    # Already an ALSA device string — use directly
    if configured.startswith(("plughw:", "hw:")):
        return configured

    # Resolve by name: read /proc/asound/cards
    logger.debug("resolve_output_device: searching for '%s'", configured)
    try:
        with open("/proc/asound/cards") as f:
            cards_text = f.read()
    except OSError:
        logger.warning("Cannot read /proc/asound/cards, using 'default'")
        return "default"

    # Parse lines like: " 3 [Generic        ]: HDA-Intel - HD-Audio Generic"
    import re
    for match in re.finditer(
        r"^\s*(\d+)\s+\[(\w+)\s*\].*?-\s*(.+)$", cards_text, re.MULTILINE
    ):
        card_num, card_id, card_desc = match.group(1), match.group(2), match.group(3)

        if (configured.lower() in card_id.lower()
                or configured.lower() in card_desc.lower()):
            # Verify this card has playback capability
            pcm_path = Path(f"/proc/asound/card{card_num}/pcm0p")
            if pcm_path.exists():
                device = f"plughw:{card_num},0"
                logger.info(
                    f"Resolved output device '{configured}' -> {device} "
                    f"({card_desc})"
                )
                return device
            else:
                logger.debug(
                    f"Card {card_num} ({card_id}) matches '{configured}' "
                    f"but has no playback"
                )

    logger.warning(
        f"Output device '{configured}' not found in ALSA cards, using 'default'"
    )
    return "default"


class TextToSpeech:
    """Text-to-speech engine supporting Kokoro and Piper backends"""

    def __init__(self, config):
        self.config = config
        self.logger = get_logger(__name__, config)

        # TTS lock to prevent concurrent calls
        self._tts_lock = threading.Lock()

        # Track active audio subprocesses for scoped interrupt/kill
        self._active_procs: list = []
        self._active_procs_lock = threading.Lock()
        self._interrupt_event = threading.Event()

        # Track whether speak() was called (for caller detection)
        self._spoke = False

        # Ack state exists for every TTS backend. Kokoro fills this cache later;
        # Piper intentionally leaves it empty. This prevents speak_ack() from
        # crashing when Piper is the active German voice engine.
        self._ack_cache: Dict[str, tuple[bytes, str]] = {}
        self._ack_played = False

        # Audio output device (resolved by name at startup)
        self.audio_device = resolve_output_device(
            config.get("audio.output_device", "default")
        )
        self.output_backend = str(
            config.get("audio.output_backend", "auto")
        ).lower()
        self.windows_temp_dir = Path(
            config.get(
                "audio.windows_temp_dir",
                "/mnt/c/Users/Alex/AppData/Local/Temp/JARVIS",
            )
        )

        # Normalization
        self.normalization_enabled = config.get("tts.normalization_enabled", True)
        self.normalizer = get_normalizer() if self.normalization_enabled else None

        # Engine selection
        self.engine = config.get("tts.engine", "piper")

        self._piper_ready = False  # Tracks whether Piper fallback is initialized

        if self.engine == "kokoro":
            self._init_kokoro(config)
        elif self.engine == "chatterbox":
            self._init_chatterbox(config)
        else:
            self._init_piper(config)
            self._piper_ready = True

        if self.normalization_enabled:
            self.logger.info("Text normalization enabled")

    # ── Kokoro initialization ──────────────────────────────────────────

    def _init_kokoro(self, config):
        """Initialize Kokoro TTS engine (in-process, CPU)."""
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*dropout option adds dropout.*")
            warnings.filterwarnings("ignore", message=".*weight_norm.*is deprecated.*")
            from kokoro import KPipeline
        import torch
        import numpy as np

        self._np = np
        self.sample_rate = 24000

        self.logger.info("Initializing Kokoro TTS pipeline...")
        t0 = time.time()
        # Force CPU — faster than GPU for this 82M model, and avoids
        # stealing the ROCm device from CTranslate2/STT
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*dropout option adds dropout.*")
            warnings.filterwarnings("ignore", message=".*weight_norm.*is deprecated.*")
            self._kokoro_pipeline = KPipeline(lang_code='b', repo_id='hexgrad/Kokoro-82M', device='cpu')

        # Load blended voice: 50% fable + 50% george
        voice_a = config.get("tts.kokoro_voice_a", "bm_fable")
        voice_b = config.get("tts.kokoro_voice_b", "bm_george")
        blend_ratio = config.get("tts.kokoro_blend_ratio", 0.5)

        voice_dir = Path(os.path.expanduser(
            "~/.cache/huggingface/hub/models--hexgrad--Kokoro-82M"
        ))
        # Find the snapshot directory dynamically
        snapshots = list((voice_dir / "snapshots").iterdir())
        if snapshots:
            voices_dir = snapshots[0] / "voices"
        else:
            raise FileNotFoundError(f"No Kokoro snapshots found in {voice_dir}")

        va = torch.load(voices_dir / f"{voice_a}.pt", weights_only=True)
        vb = torch.load(voices_dir / f"{voice_b}.pt", weights_only=True)
        self._kokoro_voice = va * blend_ratio + vb * (1.0 - blend_ratio)

        self._kokoro_speed = config.get("tts.kokoro_speed", 1.0)

        # Inject pronunciation overrides into Misaki G2P lexicon
        pronunciations = config.get("tts.kokoro_pronunciations", {})
        if pronunciations and hasattr(self._kokoro_pipeline, 'g2p'):
            golds = getattr(getattr(self._kokoro_pipeline.g2p, 'lexicon', None), 'golds', None)
            if golds is not None:
                for word, phonemes in pronunciations.items():
                    golds[word.lower()] = phonemes
                self.logger.info(f"Kokoro G2P: injected {len(pronunciations)} pronunciation override(s)")

        init_time = time.time() - t0
        self.logger.info(
            f"Kokoro TTS initialized in {init_time:.1f}s "
            f"(voice: {voice_a} {int(blend_ratio*100)}% + {voice_b} {int((1-blend_ratio)*100)}%, "
            f"speed: {self._kokoro_speed})"
        )

        # Pre-synthesize short acknowledgment phrases for instant playback
        # Maps phrase → (pcm_bytes, style_tag)
        self._ack_cache: Dict[str, tuple[bytes, str]] = {}
        self._ack_played = False
        self._build_ack_cache()

        # CAL-L0 response cache — persistent on-disk cache with SQLite catalog.
        # Loads from disk (~10ms) on startup. Only generates missing phrases.
        from core.tts_cache import TTSCache
        self._tts_cache = TTSCache(config)
        loaded = self._tts_cache.load_all()

        # Background thread generates any missing phrases (first startup
        # or new honorific added). Subsequent startups load from disk instantly.
        self._cal_l0_generating = False
        import threading
        t = threading.Thread(
            target=self._build_cal_l0_cache,
            daemon=True,
            name="cal-l0-cache",
        )
        t.start()

    # ── Piper initialization ──────────────────────────────────────────

    def _init_piper(self, config):
        """Initialize Piper TTS engine (subprocess-based)."""
        self.model_path = config.get("tts.model_path")
        self.config_path = config.get("tts.config_path")
        self.piper_bin = config.get("tts.piper_bin", "piper")

        self.length_scale = config.get("tts.length_scale", 1.0)
        self.noise_scale = config.get("tts.noise_scale", 0.667)
        self.noise_w_scale = config.get("tts.noise_w_scale", 0.8)
        self.sentence_silence = config.get("tts.sentence_silence", 0.2)

        self.sample_rate = self._get_piper_sample_rate()

        self.logger.info(f"Piper TTS initialized with model: {Path(self.model_path).name}")

    def _get_piper_sample_rate(self) -> int:
        """Read sample rate from Piper config file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    piper_config = json.load(f)
                    return piper_config.get("audio", {}).get("sample_rate", 22050)
        except Exception as e:
            self.logger.warning(f"Could not read sample rate from config: {e}")
        return 22050

    # Chatterbox service

    # How often to re-probe a server we last found unhealthy vs. healthy.
    # Asymmetric on purpose: recover fast, don't hammer a healthy server.
    _CHATTERBOX_HEALTH_RECHECK_OK = 5.0
    _CHATTERBOX_HEALTH_RECHECK_DOWN = 1.0
    _CHATTERBOX_HEALTH_TIMEOUT = 1.5
    # Circuit breaker: after this many consecutive real request failures
    # (not health-check misses — actual /tts call failures), stop trying
    # Chatterbox entirely for the cooldown period instead of paying a
    # health-check round-trip (or worse, a full request) per utterance
    # against a server that's clearly not coming back immediately.
    _CHATTERBOX_CIRCUIT_FAILURE_THRESHOLD = 3
    _CHATTERBOX_CIRCUIT_COOLDOWN = 15.0

    def _init_chatterbox(self, config):
        self.chatterbox_endpoint = config.get(
            "tts.chatterbox_endpoint",
            "http://127.0.0.1:8765/tts"
        )
        self.chatterbox_timeout = float(
            config.get("tts.chatterbox_timeout", 60)
        )
        # Separate, short connect timeout — a generation request
        # legitimately needs up to chatterbox_timeout to *complete*
        # (real GPU work), but establishing the TCP connection itself
        # should never take more than a couple seconds against a
        # server on localhost/LAN.
        self.chatterbox_connect_timeout = float(
            config.get("tts.chatterbox_connect_timeout", 2.0)
        )
        self.sample_rate = 24000

        # requests.Session (already a project dependency) instead of
        # urllib.request: reuses the underlying TCP connection across
        # sentences via connection pooling/keep-alive, instead of a
        # fresh handshake per utterance, and supports separate
        # connect/read timeouts natively.
        import requests
        self._chatterbox_session = requests.Session()

        # Throttled health-check state (see _chatterbox_available). Start
        # at 0 so the very first call always probes.
        self._chatterbox_next_health_check = 0.0
        self._chatterbox_last_health_ok = True

        # Circuit breaker state (see _chatterbox_available /
        # _chatterbox_record_failure/_success).
        self._chatterbox_consecutive_failures = 0
        self._chatterbox_circuit_open_until = 0.0

        self.logger.info(
            f"Chatterbox TTS service: {self.chatterbox_endpoint}"
        )

        # Ack cache + CAL-L0 response cache — same mechanism as Kokoro
        # (see _synthesize_short_pcm), but each phrase costs a real GPU
        # round-trip here instead of an in-process CPU call, so both run
        # in background threads and never block startup. Until they
        # complete, speak_ack()/speak_cached() simply miss and fall
        # through to normal synthesis. (_ack_cache/_ack_played are already
        # initialized in __init__ before engine dispatch.)
        from core.tts_cache import TTSCache
        self._tts_cache = TTSCache(config)
        self._tts_cache.load_all()

        # Ack cache (~9 short phrases) and CAL-L0 cache (~300 phrases) used
        # to warm up in two PARALLEL background threads, both hammering
        # the same single-threaded Chatterbox server at once. Since the
        # server processes one request at a time, a live speak() request
        # arriving during startup could end up queued behind whichever
        # warmup requests the OS already accepted first — worst case,
        # behind most of a ~300-phrase, several-minute CAL-L0 batch.
        # Now sequential in one thread: the small/urgent ack cache goes
        # first, then CAL-L0 — and CAL-L0 additionally acquires
        # _tts_lock per-phrase (see _synthesize_short_pcm_throttled), so
        # a live request only ever waits for the single in-flight warmup
        # phrase to finish, not the whole batch.
        self._cal_l0_generating = False
        if config.get("tts.chatterbox_warmup_enabled", True):
            threading.Thread(
                target=self._run_chatterbox_warmup,
                daemon=True,
                name="chatterbox-warmup",
            ).start()
        else:
            self.logger.info("Chatterbox cache warmup disabled")

    def _synthesize_short_pcm(self, text: str) -> Optional[bytes]:
        """Engine-dispatching short-phrase synth for the ack/CAL-L0 caches."""
        if self.engine == "kokoro":
            return self._synthesize_to_pcm(text)
        elif self.engine == "chatterbox":
            pcm, _sr = self._chatterbox_generate_pcm(text)
            return pcm
        return None

    def _synthesize_short_pcm_throttled(self, text: str) -> Optional[bytes]:
        """Same as _synthesize_short_pcm, but acquires _tts_lock for just
        this one phrase's synthesis instead of not at all.

        Used only for the CAL-L0 background warmup loop against
        Chatterbox: the lock is the same one speak() takes, so a live
        request contends for it fairly against the warmup loop instead
        of racing it unlocked at the HTTP level. Bounds the worst case a
        live request can be delayed by warmup to "one in-flight warmup
        phrase" (~1-3s), not the whole ~300-phrase batch — because the
        lock is acquired and released per-phrase, not held for the
        entire loop.
        """
        with self._tts_lock:
            return self._synthesize_short_pcm(text)

    def _run_chatterbox_warmup(self):
        """Build Chatterbox acknowledgement and CAL-L0 caches in background."""

        self._build_ack_cache()
        self._build_cal_l0_cache()

    def _chatterbox_health_url(self) -> str:
        base = self.chatterbox_endpoint
        if base.endswith("/tts"):
            base = base[: -len("/tts")]
        return base + "/health"

    def _chatterbox_circuit_open(self) -> bool:
        return time.monotonic() < self._chatterbox_circuit_open_until

    def _chatterbox_record_failure(self):
        """Called after a real /tts request fails (not a health-check
        miss). Opens the circuit breaker after enough consecutive
        failures so a persistently-failing server (up per /health, but
        erroring on generation) stops eating a full request per
        utterance during the cooldown."""
        self._chatterbox_consecutive_failures += 1
        if self._chatterbox_consecutive_failures >= self._CHATTERBOX_CIRCUIT_FAILURE_THRESHOLD:
            self._chatterbox_circuit_open_until = (
                time.monotonic() + self._CHATTERBOX_CIRCUIT_COOLDOWN
            )
            self.logger.warning(
                "Chatterbox circuit breaker OPEN after %d consecutive "
                "failures — skipping requests for %.0fs",
                self._chatterbox_consecutive_failures,
                self._CHATTERBOX_CIRCUIT_COOLDOWN,
            )

    def _chatterbox_record_success(self):
        self._chatterbox_consecutive_failures = 0
        self._chatterbox_circuit_open_until = 0.0

    def _chatterbox_available(self) -> bool:
        """Cheap, throttled health probe (plus circuit breaker gate).

        A dead Chatterbox server used to only be discovered by letting a
        real synthesis request run into the full chatterbox_timeout
        (default 60s) before falling back to Piper. This probes /health
        with a short timeout instead, and only re-probes periodically
        (not on every single utterance) so a healthy server pays no
        extra latency on the happy path. If the circuit breaker is open
        (repeated real request failures), skips even the health probe.
        """
        if self._chatterbox_circuit_open():
            return False

        now = time.monotonic()
        if now < self._chatterbox_next_health_check:
            return self._chatterbox_last_health_ok

        ok = False
        try:
            response = self._chatterbox_session.get(
                self._chatterbox_health_url(),
                timeout=(self.chatterbox_connect_timeout, self._CHATTERBOX_HEALTH_TIMEOUT),
            )
            ok = response.status_code == 200
        except Exception:
            ok = False

        self._chatterbox_last_health_ok = ok
        self._chatterbox_next_health_check = now + (
            self._CHATTERBOX_HEALTH_RECHECK_OK if ok
            else self._CHATTERBOX_HEALTH_RECHECK_DOWN
        )
        if not ok:
            self.logger.warning("Chatterbox health check failed — server unreachable")
        return ok

    def _chatterbox_voice_fingerprint(self) -> str:
        """Fingerprint identifying the exact voice/config a cache entry was
        generated under. tools/chatterbox_server.py is a separate process
        that doesn't share this one's config.yaml — its generation params
        (exaggeration, cfg_weight, tempo, ...) live in ITS environment, so
        the client can't assume anything about them. It asks the server
        directly via /config instead of guessing, and folds the answer
        into the cache version string — changing any of those params (or
        restarting the server with different env vars) naturally
        invalidates old CAL-L0 audio instead of silently replaying it
        under the new voice.

        Falls back to a fixed placeholder if the server can't be reached
        at init time (cache will simply regenerate once it can).
        """
        try:
            url = self.chatterbox_endpoint.rsplit("/tts", 1)[0] + "/config"
            response = self._chatterbox_session.get(
                url, timeout=(self.chatterbox_connect_timeout, 3)
            )
            cfg = response.json()
            import hashlib
            digest = hashlib.sha256(
                json.dumps(cfg, sort_keys=True).encode("utf-8")
            ).hexdigest()[:12]
            return digest
        except Exception as e:
            self.logger.warning(
                f"Could not fetch Chatterbox /config for cache fingerprint: {e}"
            )
            return "unknown"

    def _speak_chatterbox(self, text: str, timeout_override: float = None) -> bool:
        if not self._chatterbox_available():
            return False

        read_timeout = (
            timeout_override
            if timeout_override is not None
            else self.chatterbox_timeout
        )
        player = None
        try:
            t0 = time.time()

            response = self._chatterbox_session.post(
                self.chatterbox_endpoint,
                json={"text": text},
                timeout=(self.chatterbox_connect_timeout, read_timeout),
            )
            response.raise_for_status()
            wav_bytes = response.content
            if self._interrupt_event.is_set():
                return False

            if not wav_bytes.startswith(b"RIFF"):
                self.logger.error("Chatterbox returned invalid WAV data")
                self._chatterbox_record_failure()
                return False

            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                pcm = wf.readframes(wf.getnframes())

            if channels != 1 or sample_width != 2:
                self.logger.error(
                    "Unsupported Chatterbox WAV format: channels=%d width=%d",
                    channels,
                    sample_width,
                )
                self._chatterbox_record_failure()
                return False

            saved_rate = self.sample_rate
            self.sample_rate = sample_rate

            try:
                player = self._open_aplay()
                if player is None:
                    self._chatterbox_record_failure()
                    return False

                self._track_proc(player)

                player.stdin.write(pcm)
                player.stdin.close()

                rc = player.wait(timeout=30)

                if rc != 0:
                    err = player.stderr.read().decode(errors="replace").strip()
                    self.logger.error(
                        "Chatterbox playback failed (%d): %s",
                        rc,
                        err,
                    )
                    self._chatterbox_record_failure()
                    return False

            finally:
                self.sample_rate = saved_rate
                if player is not None:
                    self._untrack_proc(player)

            self._chatterbox_record_success()
            self.logger.info(
                "Chatterbox TTS completed in %.2fs",
                time.time() - t0,
            )
            return True

        except Exception as e:
            self.logger.error(f"Chatterbox TTS failed: {e}")
            self._chatterbox_record_failure()
            return False

    def _chatterbox_generate_pcm(self, text: str, timeout_override: float = None):
        """POST text to the Chatterbox server, return (pcm_bytes, sample_rate).

        Used by StreamingAudioPipeline for gapless multi-sentence playback —
        unlike _speak_chatterbox this does not play the audio itself, it
        just synthesizes so the caller can write raw PCM to a persistent
        aplay pipe. Returns (None, None) on failure — a down server or a
        single bad chunk must not silently drop that sentence; the caller
        (StreamingAudioPipeline) falls back to Piper for that one chunk.
        """
        if not self._chatterbox_available():
            return None, None

        started = time.monotonic()
        try:
            response = self._chatterbox_session.post(
                self.chatterbox_endpoint,
                json={"text": text},
                timeout=(self.chatterbox_connect_timeout,
                         timeout_override if timeout_override is not None else self.chatterbox_timeout),
            )
            wav_bytes = response.content

            if not wav_bytes.startswith(b"RIFF"):
                self.logger.error("Chatterbox returned invalid WAV data")
                self._emit_chatterbox_synthesis_event(
                    status="error",
                    text_length=len(text),
                    generation_time_s=time.monotonic() - started,
                    error_type="InvalidWav",
                )
                self._chatterbox_record_failure()
                return None, None

            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                sample_rate = wf.getframerate()
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                    self.logger.error("Unsupported Chatterbox PCM format")
                    self._emit_chatterbox_synthesis_event(
                        status="error",
                        text_length=len(text),
                        generation_time_s=time.monotonic() - started,
                        error_type="UnsupportedPcmFormat",
                    )
                    self._chatterbox_record_failure()
                    return None, None
                pcm = wf.readframes(wf.getnframes())
            self._chatterbox_record_success()
            generation_time_s = time.monotonic() - started
            self._emit_chatterbox_synthesis_event(
                status="success",
                text_length=len(text),
                generation_time_s=generation_time_s,
                audio_duration_s=len(pcm) / (sample_rate * 2) if sample_rate else 0.0,
            )
            return pcm, sample_rate

        except Exception as e:
            self._emit_chatterbox_synthesis_event(
                status="error",
                text_length=len(text),
                generation_time_s=time.monotonic() - started,
                audio_duration_s=None,
                error_type=type(e).__name__,
            )
            self.logger.error(f"Chatterbox generate failed: {e}")
            self._chatterbox_record_failure()
            return None, None

    @staticmethod
    def _emit_chatterbox_synthesis_event(
        *, status: str, text_length: int, generation_time_s: float,
        audio_duration_s: Optional[float] = None, error_type: Optional[str] = None,
    ) -> None:
        """Emit content-free per-Chatterbox-request metrics for the UI aggregates."""
        try:
            from core.event_logger import get_event_logger

            event_logger = get_event_logger()
            if not event_logger:
                return
            rtf = (
                audio_duration_s / generation_time_s
                if audio_duration_s is not None and generation_time_s > 0
                else None
            )
            event_logger.emit(
                category="inference",
                event="tts_synthesis",
                message=(
                    f"Chatterbox {status}: {audio_duration_s:.1f}s audio in {generation_time_s:.3f}s"
                    if audio_duration_s is not None
                    else f"Chatterbox {status}: {text_length} chars"
                ),
                severity="error" if status == "error" else "info",
                source="tts",
                stage="tts",
                status=status,
                latency_ms=round(generation_time_s * 1000, 1),
                duration_ms=round(generation_time_s * 1000, 1),
                model="chatterbox",
                metadata={
                    "engine": "chatterbox",
                    "text_length": text_length,
                    "generation_time_s": round(generation_time_s, 3),
                    "audio_duration_s": (
                        round(audio_duration_s, 2) if audio_duration_s is not None else None
                    ),
                    "rtf": round(rtf, 2) if rtf is not None else None,
                    **({"error_type": error_type} if error_type else {}),
                },
            )
        except Exception:
            pass  # Observability must never break TTS.

    def _resample_pcm(self, pcm_bytes: bytes, src_rate: int, dst_rate: int) -> bytes:
        """Resample 16-bit mono PCM via ffmpeg.

        Needed when a per-chunk fallback engine's native sample rate
        differs from the rate StreamingAudioPipeline already fixed for
        the open aplay session (set by whichever engine produced the
        first chunk) — writing raw PCM at the wrong rate into an aplay
        process opened with a fixed -r plays it pitch-/speed-shifted.
        Best-effort: returns the original bytes if resampling fails, so a
        chunk is never dropped over a resample error (audible glitch
        beats silence).
        """
        if src_rate == dst_rate or not pcm_bytes:
            return pcm_bytes
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "s16le", "-ac", "1", "-ar", str(src_rate), "-i", "pipe:0",
                    "-f", "s16le", "-ac", "1", "-ar", str(dst_rate), "pipe:1",
                ],
                input=pcm_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=True,
            )
            return result.stdout
        except Exception as e:
            self.logger.error(f"PCM resample failed ({src_rate}->{dst_rate}Hz): {e}")
            return pcm_bytes

    # ── Piper fallback ─────────────────────────────────────────────────

    def _ensure_piper_fallback_ready(self) -> bool:
        """Lazily initialize Piper as a fallback engine, once.

        _init_piper() sets self.sample_rate as a side effect (correct
        when Piper is the *primary* engine) — here it's just the
        fallback, so the primary engine's rate is saved/restored around
        it and Piper's own rate is kept separately in
        self._piper_sample_rate for callers that need it explicitly.
        """
        if self._piper_ready:
            return True
        try:
            self.logger.warning("Initializing Piper fallback...")
            primary_rate = self.sample_rate
            self._init_piper(self.config)
            self._piper_sample_rate = self.sample_rate
            self.sample_rate = primary_rate
            self._piper_ready = True
            return True
        except Exception as e:
            self.logger.error(f"Piper fallback init failed: {e}")
            return False

    def _fallback_to_piper(self, text: str) -> bool:
        """Attempt Piper TTS when the primary engine fails (blocking, plays
        the audio itself). Used by speak()'s single-shot path."""
        if not self._ensure_piper_fallback_ready():
            return False

        self.logger.warning("Primary TTS failed - falling back to Piper")

        if self.output_backend == "windows":
            pcm, sr = self._piper_generate_pcm(text)
            if pcm is None:
                return False
            return self._play_pcm_windows(pcm, sr)
        # _speak_piper opens its own aplay with the correct rate
        saved_rate = self.sample_rate
        self.sample_rate = getattr(self, '_piper_sample_rate', 22050)
        try:
            return self._speak_piper(text)
        finally:
            self.sample_rate = saved_rate

    def _piper_generate_pcm(self, text: str):
        """Generate raw PCM via Piper without playing it — the per-chunk
        fallback inside StreamingAudioPipeline. Returns (pcm, sample_rate)
        or (None, None) on failure, so a Chatterbox chunk failure can
        still be spoken instead of silently dropped from the response.
        """
        if not self._ensure_piper_fallback_ready():
            return None, None

        try:
            piper_cmd = [
                self.piper_bin,
                "-m", self.model_path,
                "-c", self.config_path,
                "--length-scale", str(self.length_scale),
                "--noise-scale", str(self.noise_scale),
                "--noise-w-scale", str(self.noise_w_scale),
                "--sentence-silence", str(self.sentence_silence),
                "--output-raw",
            ]
            piper = subprocess.Popen(
                piper_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._track_proc(piper)
            try:
                pcm, err = piper.communicate(
                    input=text.encode("utf-8"), timeout=15
                )
            finally:
                self._untrack_proc(piper)

            if piper.returncode != 0:
                self.logger.error(
                    "Piper fallback error (code %d): %s",
                    piper.returncode, err.decode(errors="replace"),
                )
                return None, None

            return pcm, self._piper_sample_rate

        except Exception as e:
            self.logger.error(f"Piper PCM fallback failed: {e}")
            return None, None

    # ── Shared speak interface ─────────────────────────────────────────

    def _speak_directed_chatterbox(self, plan, *, normalize: bool,
                                   cancel_check=None, timeout_override=None) -> bool:
        """Synthesize only explicit pause-separated segments, then play once."""
        if self.engine != "chatterbox":
            self.logger.warning("Voice pause direction requires Chatterbox")
            return False

        def normalize_segment(text):
            if normalize and self.normalization_enabled and self.normalizer:
                return self.normalizer.normalize(text)
            return text.strip()

        def synthesize_segment(text):
            if self._interrupt_event.is_set() or (cancel_check and cancel_check()):
                return None
            if timeout_override is None:
                pcm, rate = self._chatterbox_generate_pcm(text)
            else:
                pcm, rate = self._chatterbox_generate_pcm(text, timeout_override=timeout_override)
            if (pcm is None and not self._interrupt_event.is_set()
                    and not (cancel_check and cancel_check())):
                pcm, rate = self._piper_generate_pcm(text)
            return PcmChunk(pcm, rate) if pcm is not None and rate is not None else None

        try:
            pcm, rate = compose_directed_pcm(
                plan, synthesize_segment, normalize_segment,
                default_rate=self.sample_rate,
                resample=resample_pcm_s16le,
            )
        except (ValueError, subprocess.SubprocessError) as exc:
            self.logger.error("Directed TTS audio rejected: %s", exc)
            return False
        if pcm is None or self._interrupt_event.is_set() or (cancel_check and cancel_check()):
            return False
        if self.output_backend == "windows":
            return self._play_pcm_windows(pcm, rate)
        saved_rate = self.sample_rate
        player = None
        try:
            self.sample_rate = rate
            player = self._open_aplay()
            if player is None:
                return False
            self._track_proc(player)
            player.stdin.write(pcm)
            player.stdin.close()
            return player.wait(timeout=max(30, len(pcm) / (rate * 2) + 5)) == 0
        finally:
            self.sample_rate = saved_rate
            if player is not None:
                self._untrack_proc(player)

    def speak(self, text: str, normalize: bool = True, cancel_check=None,
              timeout_override: float = None) -> bool:
        """
        Speak text using the configured TTS engine.

        Args:
            text: Text to speak
            normalize: Whether to normalize text (default: True)
            cancel_check: Optional callable returning True to abort right
                          after the TTS lock is acquired but before any
                          synthesis starts — same re-check-after-lock
                          pattern as speak_ack(). Used by the contextual
                          ack path (core/pipeline.py) so a real response
                          that arrived while waiting for the lock isn't
                          delayed further by a now-stale ack.
            timeout_override: Caps the Chatterbox request timeout for
                               this call only (connect+read), instead of
                               the configured self.chatterbox_timeout.
                               Also used by the contextual ack path: an
                               ack must never be allowed to hold
                               _tts_lock for as long as a real response
                               synthesis legitimately can.

        Returns:
            True if successful, False otherwise
        """
        with self._tts_lock:
            if cancel_check and cancel_check():
                self.logger.debug("speak() cancelled after lock acquisition")
                return False

            if not hasattr(self, "_interrupt_event"):
                self._interrupt_event = threading.Event()
            self._interrupt_event.clear()

            if not text or not text.strip():
                self.logger.warning("Empty text provided to speak()")
                return False

            self._spoke = True
            directed = has_directions(text)
            if directed:
                plan = parse_directions(text)
                log_diagnostics(self.logger, plan.diagnostics)
                self.logger.info("TTS speak() called with voice directions")
                if plan.has_pause:
                    if self.engine == "chatterbox":
                        return self._speak_directed_chatterbox(
                            plan, normalize=normalize, cancel_check=cancel_check,
                            timeout_override=timeout_override,
                        )
                    self.logger.warning("Voice pause direction requires Chatterbox")
                text = plan.plain_text
                if not text.strip():
                    return False
            else:
                self.logger.info("TTS speak() called (%d chars)", len(text))

            # CAL-L0 cache: check for pre-generated audio before synthesizing.
            # Saves ~300ms per cached phrase. Cache key is the exact text.
            cached_pcm = self._tts_cache.get(text) if not directed and hasattr(self, "_tts_cache") else None
            if cached_pcm is not None:
                if getattr(self, "output_backend", "auto") == "windows":
                    ok = self._play_pcm_windows(
                        cached_pcm,
                        self.sample_rate,
                    )
                    if ok:
                        self.logger.info("CAL-L0 cached Windows playback (%d chars)", len(text))
                        return True
                try:
                    aplay = self._open_aplay()
                    if aplay:
                        self._track_proc(aplay)
                        aplay.stdin.write(cached_pcm)
                        aplay.stdin.close()
                        aplay.wait(timeout=10)
                        self._untrack_proc(aplay)
                        self.logger.info("CAL-L0 cached playback (%d chars)", len(text))
                        # Structured event: TTS cache hit
                        try:
                            from core.event_logger import get_event_logger
                            el = get_event_logger()
                            if el:
                                el.emit(
                                    category="performance",
                                    event="tts_cache_hit",
                                    message=f"Cache hit ({len(text)} chars)",
                                    severity="debug",
                                    source="tts",
                                    stage="tts",
                                    status="success",
                                    metadata={"text_length": len(text), "cache_type": "cal_l0"},
                                )
                        except Exception:
                            pass
                        return aplay.returncode == 0
                except Exception as e:
                    self.logger.warning(f"CAL-L0 cache playback failed, falling through: {e}")
                    # Fall through to normal synthesis

            try:
                # Normalize text for human-readable speech
                if (
                    normalize
                    and self.normalization_enabled
                    and self.normalizer
                ):
                    original_text = text
                    text = self.normalizer.normalize(text)
                    if text != original_text:
                        self.logger.debug("Normalized TTS text (%d chars)", len(text))

                if self.engine == "kokoro":
                    result = self._speak_kokoro(text)
                    if not result:
                        if self._interrupt_event.is_set():
                            return False
                        return self._fallback_to_piper(text)
                    return result
                elif self.engine == "chatterbox":
                    if getattr(self, "output_backend", "auto") == "windows":
                        result = self._speak_chatterbox_windows(
                            text, timeout_override=timeout_override
                        )
                    else:
                        result = self._speak_chatterbox(
                            text, timeout_override=timeout_override
                        )
                    if not result:
                        if self._interrupt_event.is_set():
                            return False
                        if cancel_check is not None:
                            # Bounded/cancellable call (the contextual-ack
                            # path — see _play_ack_if_still_thinking in
                            # core/pipeline.py, the only caller that passes
                            # cancel_check). Falling back to Piper here
                            # would mean a Chatterbox timeout/failure just
                            # trades one slow engine for another — the
                            # exact "stale Piper ack" this bound exists to
                            # prevent, and it would still hold _tts_lock
                            # for the full Piper synthesis+playback,
                            # delaying the real response regardless. An
                            # ack is best-effort by design: drop it
                            # silently instead. Real (non-ack) speak()
                            # calls never pass cancel_check, so their
                            # Piper fallback is completely unchanged below.
                            self.logger.debug(
                                "Bounded speak() call: Chatterbox failed/"
                                "timed out — dropping instead of falling "
                                "back to Piper"
                            )
                            return False
                        return self._fallback_to_piper(text)
                    return result
                else:
                    if self._interrupt_event.is_set():
                        return False
                    return self._speak_piper(text)

            except Exception as e:
                self.logger.error(f"TTS error: {e}")
                return False

    # ── Acknowledgment cache ─────────────────────────────────────────

    def _build_ack_cache(self):
        """Pre-synthesize short phrases as raw PCM for instant playback.

        Builds into a local dict and publishes it with a single atomic
        reference swap at the end (self._ack_cache = new_cache), rather
        than mutating self._ack_cache in place. For Chatterbox this runs
        in a background thread while speak_ack() may concurrently read
        the cache from the main thread — incremental mutation risked a
        "dict changed size during iteration" crash if a read landed
        mid-build; a full dict is either fully old or fully new, never
        half-built, so no lock is needed for that part.

        Chatterbox additionally uses the throttled (per-phrase _tts_lock)
        synth path, same as the CAL-L0 warmup right after it — without
        this, the ~9 ack phrases hit the Chatterbox server completely
        unlocked, so a live speak() during just this early phase of
        warmup wasn't actually protected despite _run_chatterbox_warmup's
        docstring claiming it was.
        """
        from core import persona
        tagged_phrases = persona.pool_tagged("ack_cache")
        new_cache: Dict[str, tuple[bytes, str]] = {}
        synth_fn = (
            self._synthesize_short_pcm_throttled if self.engine == "chatterbox"
            else self._synthesize_short_pcm
        )
        t0 = time.time()
        for phrase, style in tagged_phrases:
            try:
                pcm = synth_fn(phrase)
                if pcm:
                    new_cache[phrase] = (pcm, style)
            except Exception as e:
                self.logger.warning(f"Failed to cache ack phrase '{phrase}': {e}")

        self._ack_cache = new_cache
        elapsed = time.time() - t0
        self.logger.info(
            f"Ack cache: {len(self._ack_cache)} phrases pre-synthesized in {elapsed:.1f}s"
        )

    # ── CAL-L0 response cache ─────────────────────────────────────────

    # All response templates from the conversation skill.
    # {honorific} placeholder gets resolved per-honorific during cache build.
    _CAL_L0_TEMPLATES = [
        # Greetings — presence detection pools (must match persona.py pools)
        "Good morning, {honorific}.",
        "Morning, {honorific}.",
        "Good morning, {honorific}. I trust you slept well.",
        "Morning, {honorific}. Another day, another opportunity.",
        "Good to see you up and about, {honorific}.",
        "Good morning, {honorific}, I hope the coffee is strong.",
        "Good afternoon, {honorific}.",
        "Afternoon, {honorific}.",
        "Good afternoon, {honorific}, I hope the day is treating you well.",
        "Afternoon, {honorific}. Productive day so far, I hope.",
        "Good afternoon, {honorific}, good to see you.",
        "Afternoon, {honorific}, what can I do for you?",
        "Good evening, {honorific}.",
        "Evening, {honorific}.",
        "Good evening, {honorific}. Winding down, or just getting started?",
        "Evening, {honorific}. I trust the day went well.",
        "Good evening, {honorific}, good to have you back.",
        "Evening, {honorific}, what can I do for you?",
        "Good evening, {honorific}. I was beginning to wonder if you'd forgotten about me.",
        # Return greetings
        "Welcome back, {honorific}.",
        "There you are, {honorific}. Good to see you.",
        "Welcome back, {honorific}. I kept everything running while you were away.",
        "Ah, {honorific}, welcome back.",
        "Good to see you again, {honorific}.",
        "Welcome back, {honorific}, I missed having someone to talk to.",
        "There he is. Welcome back, {honorific}.",
        # Return with reminders
        "Welcome back, {honorific}. A few things came up while you were away, want me to go through them?",
        "There you are, {honorific}. I held a few reminders for you, want to hear them?",
        "Welcome back, {honorific}, you have some pending reminders. Shall I go through them?",
        "Ah, {honorific}, welcome back. A couple of things to catch you up on, whenever you're ready.",
        "Welcome back, {honorific}. I've been holding onto a few items for you.",
        # Late night
        "Burning the midnight oil, I see.",
        "Still at it, {honorific}? I admire the dedication.",
        "Evening, {honorific}. I should point out it's well past a reasonable hour.",
        # Generic greetings
        "Hello, {honorific}.",
        "At your service, {honorific}.",
        # Minimal greetings
        "How can I help, {honorific}?",
        "Standing by, {honorific}.",
        "I'm listening, {honorific}.",
        "What do you need, {honorific}?",
        "Go ahead, {honorific}.",
        # Farewells
        "Have a good morning, {honorific}.",
        "Until next time, {honorific}.",
        "Take care, {honorific}. I'll be here when you need me.",
        "Good luck out there, {honorific}.",
        "I'll hold down the fort, {honorific}.",
        "Have a good day, {honorific}.",
        "Take care, {honorific}.",
        "I'll be here when you need me, {honorific}.",
        "Have a productive afternoon, {honorific}.",
        "Don't be a stranger, {honorific}.",
        "Have a good evening, {honorific}.",
        "Goodnight, {honorific}.",
        "Sleep well, {honorific}.",
        "Have a restful evening, {honorific}.",
        "Until tomorrow, {honorific}. Try to get some rest.",
        "Goodnight, {honorific}. I'll keep an eye on things.",
        # Thanks
        "You're welcome, {honorific}.",
        "My pleasure, {honorific}.",
        "Of course, {honorific}.",
        "Happy to help, {honorific}.",
        "Anytime, {honorific}.",
        "Not a problem, {honorific}.",
        "Always happy to assist, {honorific}.",
        "Glad to be of service.",
        "That's what I'm here for, {honorific}.",
        "No trouble at all.",
        "Happy to oblige, {honorific}.",
        "Think nothing of it, {honorific}.",
        "It's what I do, {honorific}.",
        "Delighted to be of help.",
        "All part of the service, {honorific}.",
        # Acknowledgments
        "Indeed, {honorific}.",
        "Quite so.",
        "Precisely, {honorific}.",
        "Very good, {honorific}.",
        "Understood.",
        "Noted, {honorific}.",
        "Absolutely, {honorific}.",
        "Right you are, {honorific}.",
        "As it should be, {honorific}.",
        # Pleasantries
        "All systems operational, {honorific}.",
        "Functioning within normal parameters.",
        "Quite well, thank you for asking.",
        "Operating at full capacity, as always.",
        "All systems nominal, {honorific}.",
        "Functioning perfectly, {honorific}. No complaints.",
        "Running smoothly, {honorific}.",
        "Can't complain. Well, I could, but it wouldn't be very British of me.",
        "Everything's in order, {honorific}.",
        "All good here, {honorific}.",
        "Rather well, all things considered.",
        "Tip-top, {honorific}. Thank you for asking.",
        "Perfectly adequate, {honorific}. Which is about as enthusiastic as I get.",
        # Compliments
        "Thank you, {honorific}. I do my best.",
        "Most kind of you, {honorific}.",
        "I appreciate that, {honorific}.",
        "You're too kind, {honorific}.",
        "Glad I could help, {honorific}.",
        "That means a great deal, {honorific}. Thank you.",
        "Happy to meet expectations, {honorific}.",
        "I'll try not to let it go to my head, {honorific}.",
        "All in a day's work, {honorific}.",
        "I'm rather pleased to hear that.",
        "You'll make my circuits blush, {honorific}.",
        "I appreciate the kind words, {honorific}.",
        # Apologies
        "No need to apologize, {honorific}.",
        "No worries at all, {honorific}.",
        "That's perfectly fine, {honorific}.",
        "Think nothing of it, {honorific}.",
        "Not a problem in the slightest.",
        "No harm done, {honorific}.",
        "These things happen, {honorific}.",
        "Please, don't give it a second thought.",
        "Quite alright, {honorific}.",
        "Nothing to apologize for, {honorific}.",
        # User is good
        "Glad to hear it, {honorific}.",
        "Excellent, {honorific}.",
        "Good to hear, {honorific}.",
        "Splendid.",
        "Pleased to hear it, {honorific}.",
        "That's good to know, {honorific}.",
        "Wonderful, {honorific}.",
        # You're welcome
        "Thank you, {honorific}.",
        "Most kind, {honorific}.",
        "Appreciated, {honorific}.",
        "Very gracious of you, {honorific}.",
        "You're too kind, {honorific}. Though I won't stop you.",
        # No help needed
        "Very well, {honorific}. I'll be here if you need me.",
        "Understood, {honorific}. I'll be here when you need me.",
        "Of course, {honorific}. Just say the word.",
        "Very good, {honorific}. Standing by.",
        "Alright, {honorific}. I'm here if anything comes up.",
        "No problem, {honorific}. You know where to find me.",
        "Understood. I'll try not to take it personally, {honorific}.",
        "Right, {honorific}. I'll just be here. Waiting. Patiently.",
        "Understood, {honorific}. Standing by.",
        "Alright, {honorific}. I'm here if you need anything.",
        "Right then, {honorific}. Just say the word.",
        # Small talk
        "I'm here if you need a distraction, {honorific}.",
        "I may not be the most entertaining company, but I'm reliable.",
        "I could recite pi to a thousand digits, if that helps.",
        "Might I suggest asking me something? I do enjoy being useful.",
        "Well, {honorific}, I'm at your disposal. Name your diversion.",
        "I'm better at tasks than entertainment, but I'll give it my best.",
        "If it helps, I find your company rather enjoyable as well.",
        "I'm told I have a dry wit. Whether that's a compliment remains unclear.",
        "I'm here, {honorific}. For whatever that's worth.",
        "Perhaps I can help with something productive? Just a thought.",
        # Meta-questions
        "I'm JARVIS — a personal voice assistant, built right here at home. How can I help, {honorific}?",
        "I'm your personal assistant, {honorific}. Voice-activated, locally hosted, and at your service.",
        "JARVIS, {honorific}. Personal assistant. I handle weather, reminders, news, system tasks, and quite a bit more.",
        "I'm an AI assistant running on local hardware, {honorific}. No cloud required.",
        "I'm JARVIS. I was built to be helpful, {honorific}, and I take the job seriously.",
        "Personal assistant, {honorific}. Built from scratch, runs on your hardware, answers to you.",
        "I'm the voice in the room that actually listens, {honorific}. What would you like to know?",
        "JARVIS, at your service. I handle tasks, answer questions, and try not to be insufferable about it.",
        # What's up
        "Not much, {honorific}. Ready to assist.",
        "All quiet on the home front, {honorific}.",
        "Standing by, {honorific}. What do you need?",
        "Just monitoring systems, {honorific}. The usual.",
        "The usual, {honorific}. What can I do for you?",
        "Keeping things running smoothly, {honorific}.",
        "Nothing out of the ordinary, {honorific}. How can I help?",
        "All systems humming along nicely. What's on your mind?",
        "Keeping an eye on things, {honorific}. What do you need?",
        "Same as always, {honorific}. Ready when you are.",
        "Oh, you know. Processing data, contemplating existence. The usual.",
        "Just here, eagerly awaiting your commands, {honorific}.",
    ]

    # Primary honorifics to pre-generate at startup
    _CAL_L0_PRIMARY_HONORIFICS = ["sir", "ma'am"]

    # Bump when the cache's on-disk format or the fingerprinting scheme
    # itself changes (not for ordinary voice-parameter tweaks — those are
    # already covered by _cache_voice_version()'s fingerprint).
    _CAL_L0_SCHEMA_VERSION = "6"

    def _cache_voice_version(self) -> str:
        """Deterministic cache-version string identifying engine + voice.

        Any change that alters what the cached audio actually sounds like
        (switching tts.engine, changing Kokoro's voice blend, restarting
        Chatterbox with different exaggeration/cfg_weight/tempo/etc.) must
        invalidate old cache entries instead of silently replaying stale
        audio under the new configuration. Folds an engine-specific
        fingerprint into the version string TTSCache already uses to
        detect and purge stale entries.
        """
        if self.engine == "chatterbox":
            fingerprint = self._chatterbox_voice_fingerprint()
        elif self.engine == "kokoro":
            import hashlib
            raw = json.dumps({
                "voice_a": self.config.get("tts.kokoro_voice_a", "bm_fable"),
                "voice_b": self.config.get("tts.kokoro_voice_b", "bm_george"),
                "blend_ratio": self.config.get("tts.kokoro_blend_ratio", 0.5),
                "speed": self.config.get("tts.kokoro_speed", 1.0),
            }, sort_keys=True)
            fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        else:
            fingerprint = "n/a"
        return f"{self._CAL_L0_SCHEMA_VERSION}-{self.engine}-{fingerprint}"

    def _build_cal_l0_cache(self):
        """Generate any missing CAL-L0 response audio via TTSCache.

        Runs in a background thread after startup. On first ever startup,
        generates all 308 phrases (~200s throttled). On subsequent startups,
        load_all() already loaded from disk — this just fills gaps (new
        honorific, new template). Typically completes in 0s.
        """
        self._cal_l0_generating = True
        _t0 = time.time()
        # Chatterbox: throttled (per-phrase _tts_lock) so this ~300-phrase
        # batch can't starve a live speak() request queued behind it.
        # Kokoro is an in-process CPU call with no shared server to
        # contend over — no throttling needed there.
        synth_fn = (
            self._synthesize_short_pcm_throttled if self.engine == "chatterbox"
            else self._synthesize_short_pcm
        )
        generated = self._tts_cache.generate_missing(
            templates=self._CAL_L0_TEMPLATES,
            honorifics=self._CAL_L0_PRIMARY_HONORIFICS,
            synthesize_fn=synth_fn,
            version=self._cache_voice_version(),
            throttle_sleep=0.05,
        )
        self._cal_l0_generating = False
        self.logger.info(
            "CAL-L0 cache complete: %d phrases in %.1fs", generated, time.time() - _t0,
        )

    def _synthesize_to_pcm(self, text: str) -> bytes | None:
        """Synthesize text to raw PCM bytes via Kokoro. Returns None on failure.

        Applies trim + fade to eliminate trailing silence and wisp artifacts.
        """
        try:
            chunks = []
            for gs, ps, audio in self._kokoro_pipeline(
                text, voice=self._kokoro_voice, speed=self._kokoro_speed
            ):
                chunks.append(audio)
            if chunks:
                full = self._np.concatenate(chunks)
                full = self._trim_trailing_silence(full)
                full = self._apply_fade(full)
                return (full * 32767).astype(self._np.int16).tobytes()
        except Exception as e:
            self.logger.warning("CAL-L0 cache synthesis failed (%d chars, %s)",
                                len(text), type(e).__name__)
        return None

    def cache_cal_l0_phrase(self, text: str, pcm: bytes):
        """Lazy-cache a CAL-L0 phrase after first synthesis (for non-primary honorifics)."""
        self._tts_cache.put(text, pcm, template="", honorific="", mood="neutral")

    def speak_cached(self, text: str) -> bool:
        """Play a pre-cached CAL-L0 response. Returns False if not cached.

        Caller should fall back to speak() if this returns False.
        """
        pcm = self._tts_cache.get(text)
        if pcm is None:
            return False

        with self._tts_lock:
            if self.output_backend == "windows":
                ok = self._play_pcm_windows(
                    pcm,
                    self.sample_rate,
                )
                if ok:
                    self.logger.info(
                        "CAL-L0 cached Windows playback (%d chars)", len(text)
                    )
                return ok

            try:
                aplay = self._open_aplay()
                if aplay is None:
                    self.logger.error("speak_cached: failed to open audio device")
                    return False
                self._track_proc(aplay)
                aplay.stdin.write(pcm)
                aplay.stdin.close()
                aplay.wait(timeout=10)
                self._untrack_proc(aplay)
                self.logger.info("CAL-L0 cached playback (%d chars)", len(text))
                return aplay.returncode == 0
            except Exception as e:
                self.logger.error(f"speak_cached failed: {e}")
                if aplay is not None:
                    self._untrack_proc(aplay)
                return False

    def generate_wav(self, text: str, normalize: bool = True) -> bytes:
        """Generate WAV audio from text without playing it.

        Uses Kokoro to synthesize speech and returns a complete WAV file
        as bytes (24kHz, mono, int16). Does NOT acquire _tts_lock — no
        audio hardware is touched.

        Args:
            text: Text to synthesize
            normalize: Whether to apply TTS normalization (default: True)

        Returns:
            WAV file as bytes, or empty bytes on failure

        Raises:
            RuntimeError: If engine is not Kokoro
        """
        if self.engine != "kokoro":
            raise RuntimeError("generate_wav() requires Kokoro engine")

        if not text or not text.strip():
            return b""

        if normalize and self.normalization_enabled and self.normalizer:
            text = self.normalizer.normalize(text)

        import io
        import wave

        chunks = []
        for gs, ps, audio in self._kokoro_pipeline(
            text, voice=self._kokoro_voice, speed=self._kokoro_speed
        ):
            chunks.append(self._np.asarray(audio))

        if not chunks:
            return b""

        full = self._np.concatenate(chunks)
        int16 = (full * 32767).astype(self._np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(int16.tobytes())

        return buf.getvalue()

    def speak_ack(self, style_hint: str = None, cancel_check=None) -> bool:
        """Play a random pre-cached acknowledgment phrase instantly.

        Args:
            style_hint: Preferred style tag ("checking", "working", "research").
                        Falls back to "neutral" if no match, then any phrase.
            cancel_check: Optional callable returning True to abort after
                          acquiring the TTS lock (prevents stale acks when
                          the response arrived while waiting for the lock).

        Returns True if played, False if cache empty or playback failed.
        Call this when the LLM is slow to respond to fill the silence.
        """
        # Snapshot the reference once. _build_ack_cache() (possibly running
        # concurrently in a background thread for Chatterbox) publishes a
        # brand-new dict via a single atomic assignment rather than
        # mutating the existing one — as long as we read self._ack_cache
        # exactly once and use that local `cache` throughout, we either
        # see the fully-old or fully-new dict, never a half-built one.
        cache = self._ack_cache
        if not cache:
            return False

        with self._tts_lock:
            # Recheck after acquiring lock — response may have arrived
            # while we were blocked waiting for the lock (race fix).
            if cancel_check and cancel_check():
                self.logger.debug("Ack cancelled after lock acquisition")
                return False

            # Filter candidates by style hint (with neutral fallback)
            if style_hint:
                candidates = [p for p, (_, s) in cache.items()
                              if s == style_hint]
                if not candidates:
                    candidates = [p for p, (_, s) in cache.items()
                                  if s == "neutral"]
            else:
                candidates = list(cache.keys())
            if not candidates:
                candidates = list(cache.keys())

            phrase = random.choice(candidates)
            pcm, style = cache[phrase]
            self.logger.info(f"Ack: '{phrase}' (style={style})")

            if self.output_backend == "windows":
                ok = self._play_pcm_windows(
                    pcm,
                    self.sample_rate,
                )
                if ok:
                    self._ack_played = True
                return ok

            try:
                aplay = self._open_aplay()
                if aplay is None:
                    self.logger.error("Ack: failed to open audio device")
                    return False
                self._track_proc(aplay)
                aplay.stdin.write(pcm)
                aplay.stdin.close()
                # Set flag immediately — audio is committed to the pipe.
                # Must be visible to the streaming thread BEFORE aplay finishes,
                # otherwise the first LLM chunk races past the strip check.
                self._ack_played = True
                aplay.wait(timeout=5)
                self._untrack_proc(aplay)
                return aplay.returncode == 0
            except Exception as e:
                self.logger.error(f"Ack playback failed: {e}")
                if aplay is not None:
                    self._untrack_proc(aplay)
                return False

    @property
    def ack_played(self) -> bool:
        """Whether an ack phrase was played since last clear."""
        return self._ack_played

    def clear_ack_played(self):
        """Reset the ack-played flag (call after first LLM chunk is processed)."""
        self._ack_played = False

    # ── Scoped subprocess control ─────────────────────────────────────

    def _play_wav_windows(self, wav_bytes: bytes) -> bool:
        """Play a complete WAV through the native Windows audio stack."""
        import uuid

        if not wav_bytes:
            return False

        self.windows_temp_dir.mkdir(parents=True, exist_ok=True)
        wav_path = self.windows_temp_dir / f"jarvis-{uuid.uuid4().hex}.wav"
        wav_path.write_bytes(wav_bytes)

        proc = None
        try:
            result = subprocess.run(
                ["wslpath", "-w", str(wav_path)],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            windows_path = result.stdout.strip()

            ps_path = windows_path.replace("'", "''")
            ps = (
                f"$p='{ps_path}';"
                "$sp=[System.Media.SoundPlayer]::new($p);"
                "try{$sp.Load();$sp.PlaySync()}"
                "finally{$sp.Dispose()}"
            )

            proc = subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    ps,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._track_proc(proc)

            try:
                rc = proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.logger.error("Windows audio playback timed out")
                return False

            if rc != 0:
                err = proc.stderr.read().decode(errors="replace").strip()
                self.logger.error(
                    "Windows audio playback failed (%d): %s",
                    rc,
                    err,
                )
                return False

            return True

        except Exception as e:
            self.logger.error(f"Windows audio playback failed: {e}")
            return False

        finally:
            if proc is not None:
                self._untrack_proc(proc)
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _play_pcm_windows(
        self,
        pcm: bytes,
        sample_rate: int | None = None,
        channels: int = 1,
        sample_width: int = 2,
    ) -> bool:
        """Wrap raw PCM as WAV and play it through Windows."""
        if not pcm:
            return False

        rate = int(sample_rate or self.sample_rate)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm)

        return self._play_wav_windows(buf.getvalue())

    def _speak_chatterbox_windows(self, text: str, timeout_override: float = None) -> bool:
        """Generate with Chatterbox in WSL, play the WAV natively in Windows."""
        if not self._chatterbox_available():
            return False

        read_timeout = (
            timeout_override
            if timeout_override is not None
            else self.chatterbox_timeout
        )

        try:
            t0 = time.time()

            response = self._chatterbox_session.post(
                self.chatterbox_endpoint,
                json={"text": text},
                timeout=(
                    self.chatterbox_connect_timeout,
                    read_timeout,
                ),
            )
            response.raise_for_status()
            wav_bytes = response.content
            if self._interrupt_event.is_set():
                return False

            if not wav_bytes.startswith(b"RIFF"):
                self.logger.error("Chatterbox returned invalid WAV data")
                self._chatterbox_record_failure()
                return False

            ok = self._play_wav_windows(wav_bytes)

            if not ok:
                self._chatterbox_record_failure()
                return False

            self._chatterbox_record_success()
            self.logger.info(
                "Chatterbox Windows TTS completed in %.2fs",
                time.time() - t0,
            )
            return True

        except Exception as e:
            self.logger.error(f"Chatterbox Windows TTS failed: {e}")
            self._chatterbox_record_failure()
            return False

    def _track_proc(self, proc):
        """Register an audio subprocess for scoped interrupt control."""
        if not hasattr(self, "_interrupt_event"):
            self._interrupt_event = threading.Event()
        with self._active_procs_lock:
            self._active_procs.append(proc)
            interrupted = self._interrupt_event.is_set()
        if interrupted:
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=2)
            except Exception:
                pass
            self._untrack_proc(proc)

    def _untrack_proc(self, proc):
        """Unregister an audio subprocess after it finishes."""
        with self._active_procs_lock:
            try:
                self._active_procs.remove(proc)
            except ValueError:
                pass

    def kill_active(self):
        """Kill all tracked audio subprocesses (scoped, no global pkill)."""
        with self._active_procs_lock:
            procs = list(self._active_procs)
            self._active_procs.clear()
        for proc in procs:
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=2)
                    self.logger.info(f"Killed audio subprocess pid={proc.pid}")
            except Exception as e:
                self.logger.warning(f"Failed to kill audio subprocess: {e}")

    def interrupt_active(self):
        """Cancel the active speak operation and stop tracked playback."""
        self._interrupt_event.set()
        self.kill_active()

    # ── Kokoro speak ──────────────────────────────────────────────────

    def _raw_playback_cmd(self, sample_rate: int | None = None) -> list[str]:
        """Return the native raw-audio playback command for this output."""
        rate = int(sample_rate or self.sample_rate)

        # WSLg / PulseAudio / PipeWire:
        # use Pulse natively instead of ALSA -> Pulse emulation.
        if self.audio_device in ("pulse", "pipewire"):
            return [
                "pacat",
                "--playback",
                "--raw",
                f"--rate={rate}",
                "--channels=1",
                "--format=s16le",
            ]

        # Real ALSA device.
        return [
            "aplay",
            "-D", self.audio_device,
            "-t", "raw",
            "-r", str(rate),
            "-c", "1",
            "-f", "S16_LE",
        ]

    def _open_aplay(self, max_retries: int = 5, retry_delay: float = 0.5):
        """Open the configured raw-audio playback process.

        Pulse/PipeWire uses pacat directly. Real ALSA devices use aplay.
        """
        cmd = self._raw_playback_cmd()

        for attempt in range(max_retries):
            self.logger.debug(
                "audio open: attempt %d/%d device=%s cmd=%s",
                attempt + 1,
                max_retries,
                self.audio_device,
                cmd[0],
            )

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )

                # Give the backend a moment to fail immediately if the
                # requested device is unavailable.
                time.sleep(0.05)

                if proc.poll() is None:
                    return proc

                err = proc.stderr.read().decode(errors="replace").strip()
                self.logger.warning(
                    "Audio backend %s failed to open: %s",
                    cmd[0],
                    err or f"exit code {proc.returncode}",
                )

            except Exception as e:
                self.logger.warning(
                    "Audio backend %s open failed: %s",
                    cmd[0],
                    e,
                )

            if attempt + 1 < max_retries:
                time.sleep(retry_delay)

        return None

    def _trim_trailing_silence(self, audio_np, threshold=0.01, keep_ms=150):
        """Trim trailing silence from an audio chunk, keeping keep_ms of it.

        Reduces the long comma/clause pauses Kokoro inserts between segments
        while preserving a natural brief gap.
        """
        abs_audio = self._np.abs(audio_np)
        above = self._np.where(abs_audio > threshold)[0]
        if len(above) == 0:
            return audio_np
        last_sound = above[-1]
        keep_samples = int(24000 * keep_ms / 1000)
        trim_point = min(last_sound + keep_samples, len(audio_np))
        return audio_np[:trim_point]

    def _compress_pauses(self, audio_np, max_silence_ms=50, threshold=0.015):
        """Squeeze mid-utterance silences to max_silence_ms.

        Kokoro inserts prosodic pauses at clause boundaries (commas, titles,
        etc.) that sound robotic.  This keeps the natural prosody but caps
        how long any interior silence can last.
        """
        np = self._np
        sr = self.sample_rate
        window = int(sr * 0.01)  # 10ms analysis window
        max_silence_samples = int(sr * max_silence_ms / 1000)
        n_windows = len(audio_np) // window
        if n_windows < 2:
            return audio_np

        rms = np.array([
            np.sqrt(np.mean(audio_np[i * window:(i + 1) * window] ** 2))
            for i in range(n_windows)
        ])
        voiced = np.where(rms >= threshold)[0]
        if len(voiced) < 2:
            return audio_np
        first_voiced = voiced[0]
        last_voiced = voiced[-1]

        result = [audio_np[:first_voiced * window]]
        silent_run = 0
        for i in range(first_voiced, last_voiced + 1):
            chunk = audio_np[i * window:(i + 1) * window]
            if rms[i] < threshold:
                silent_run += window
                if silent_run <= max_silence_samples:
                    result.append(chunk)
            else:
                silent_run = 0
                result.append(chunk)
        result.append(audio_np[(last_voiced + 1) * window:])
        return np.concatenate(result)

    def _apply_fade(self, audio_np, fade_ms=3):
        """Apply fade-in and fade-out to an audio chunk.

        Eliminates wisp artifacts from Kokoro's ISTFTNet vocoder at chunk
        boundaries. 3ms is the sweet spot from VOQR research — long enough
        to suppress transients, short enough to be inaudible.
        """
        np = self._np
        fade_samples = int(self.sample_rate * fade_ms / 1000)
        if len(audio_np) < fade_samples * 2:
            return audio_np
        fade_in = np.linspace(0.0, 1.0, fade_samples, dtype=audio_np.dtype)
        fade_out = np.linspace(1.0, 0.0, fade_samples, dtype=audio_np.dtype)
        audio_np = audio_np.copy()
        audio_np[:fade_samples] *= fade_in
        audio_np[-fade_samples:] *= fade_out
        return audio_np

    def _speak_kokoro(self, text: str) -> bool:
        """Generate and play audio via Kokoro — streaming with lazy aplay.

        Defers aplay open until the first Kokoro chunk is ready so that
        PipeWire has Kokoro-generation time (~200ms+) to release the ALSA
        device after any previous playback.  This eliminates the multi-second
        gap between device open and first data write that caused
        'Device or resource busy' failures.
        """
        t0 = time.time()

        aplay = None
        total_samples = 0
        first_chunk_time = None
        stdin_closed = False
        pipe_error = False
        try:
            for gs, ps, audio in self._kokoro_pipeline(
                text, voice=self._kokoro_voice, speed=self._kokoro_speed
            ):
                audio_np = self._np.asarray(audio)
                audio_np = self._trim_trailing_silence(audio_np)
                audio_np = self._apply_fade(audio_np)
                pcm = (audio_np * 32767).astype(self._np.int16).tobytes()
                self.logger.debug("Kokoro chunk: %d samples, pcm=%d bytes",
                                  len(audio_np), len(pcm))

                # Lazy open: defer aplay until first audio is ready.
                # Gives PipeWire time to release the device.
                if aplay is None:
                    first_chunk_time = time.time() - t0
                    self.logger.info(f"Kokoro first chunk in {first_chunk_time:.3f}s")
                    aplay = self._open_aplay()
                    if aplay is None:
                        self.logger.error("Failed to open audio device after retries")
                        return False
                    self._track_proc(aplay)

                aplay.stdin.write(pcm)
                total_samples += len(audio)
        except BrokenPipeError:
            self.logger.error("aplay broken pipe (device busy?)")
            pipe_error = True
        finally:
            # Single cleanup path for aplay stdin — close exactly once.
            if aplay is not None and not stdin_closed:
                try:
                    aplay.stdin.close()
                except BrokenPipeError:
                    pass  # Already broken, close is best-effort
                stdin_closed = True

        if pipe_error:
            if aplay is not None:
                try:
                    aplay_err = aplay.stderr.read().decode().strip()
                    self.logger.error(f"aplay stderr: {aplay_err}")
                except Exception:
                    pass
                aplay.kill()
                try:
                    aplay.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.logger.warning("aplay did not exit after kill — zombie possible")
                self._untrack_proc(aplay)
            return False

        if total_samples == 0:
            self.logger.error("Kokoro produced no audio")
            if aplay is not None:
                aplay.kill()
                try:
                    aplay.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.logger.warning("aplay did not exit after kill — zombie possible")
                self._untrack_proc(aplay)
            return False

        gen_time = time.time() - t0
        duration = total_samples / self.sample_rate
        self.logger.info(
            f"Kokoro streamed {duration:.1f}s audio in {gen_time:.3f}s "
            f"(RTF: {duration/gen_time:.1f}x)"
        )

        try:
            aplay_return = aplay.wait(timeout=max(15, duration + 5))
        except subprocess.TimeoutExpired:
            self.logger.error("aplay timed out — killing")
            aplay.kill()
            aplay.wait()
            return False
        finally:
            self._untrack_proc(aplay)

        if aplay_return != 0:
            aplay_err = aplay.stderr.read().decode()
            self.logger.error(f"aplay error (code {aplay_return}): {aplay_err}")
            return False

        self.logger.info("TTS playback completed successfully")
        # Structured event: TTS synthesis completed
        try:
            from core.event_logger import get_event_logger
            el = get_event_logger()
            if el:
                el.emit(
                    category="inference",
                    event="tts_synthesis",
                    message=f"Kokoro: {duration:.1f}s audio in {gen_time:.3f}s (RTF {duration/gen_time:.1f}x)",
                    severity="info",
                    source="tts",
                    stage="tts",
                    status="success",
                    latency_ms=round(gen_time * 1000, 1),
                    metadata={
                        "engine": "kokoro",
                        "audio_duration_s": round(duration, 2),
                        "generation_time_s": round(gen_time, 3),
                        "rtf": round(duration / gen_time, 2) if gen_time > 0 else 0,
                        "ttfc_s": round(first_chunk_time, 3) if first_chunk_time else None,
                        "total_samples": total_samples,
                        "text_length": len(text),
                    },
                )
        except Exception:
            pass
        return True

    # ── Piper speak ───────────────────────────────────────────────────

    def _speak_piper(self, text: str) -> bool:
        """Generate and play audio via Piper subprocess."""
        try:
            self.logger.info("Starting Piper subprocess...")

            piper_cmd = [
                self.piper_bin,
                "-m", self.model_path,
                "-c", self.config_path,
                "--length-scale", str(self.length_scale),
                "--noise-scale", str(self.noise_scale),
                "--noise-w-scale", str(self.noise_w_scale),
                "--sentence-silence", str(self.sentence_silence),
                "--output-raw",
            ]

            piper = subprocess.Popen(
                piper_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._track_proc(piper)

            aplay_cmd = self._raw_playback_cmd(self.sample_rate)

            aplay = subprocess.Popen(
                aplay_cmd,
                stdin=piper.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._track_proc(aplay)

            piper.stdin.write(text.encode("utf-8"))
            piper.stdin.close()

            self.logger.info("Waiting for playback...")

            try:
                aplay_return = aplay.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.logger.error("aplay timed out after 15s (audio device likely busy) — killing")
                aplay.kill()
                aplay.wait()
                piper.kill()
                piper.wait()
                return False
            finally:
                self._untrack_proc(aplay)
                self._untrack_proc(piper)

            piper_return = piper.wait(timeout=5)

            if piper_return != 0:
                piper_err = piper.stderr.read().decode()
                self.logger.error(f"Piper error (code {piper_return}): {piper_err}")
                return False

            if aplay_return != 0:
                aplay_err = aplay.stderr.read().decode()
                self.logger.error(f"aplay error (code {aplay_return}): {aplay_err}")
                return False

            self.logger.info("TTS playback completed successfully")
            return True

        except FileNotFoundError as e:
            self.logger.error(f"TTS binary not found: {e}")
            self.logger.error("Please ensure Piper is installed and in PATH")
            return False

    def test(self) -> bool:
        """Test TTS system."""
        self.logger.info(f"Testing TTS system (engine: {self.engine})...")

        test_phrases = [
            "Hello, I am Jarvis.",
            "System initialized successfully.",
            "The system is running at 192.168.1.1 on port 8080.",
        ]

        for phrase in test_phrases:
            self.logger.info(f"Speaking: {phrase}")
            if not self.speak(phrase):
                self.logger.error("TTS test failed")
                return False

        self.logger.info("TTS test completed successfully")
        return True


# Convenience function for quick TTS
def speak(text: str, config=None) -> bool:
    """Quick speak function."""
    if config is None:
        from core.config import get_config
        try:
            config = get_config()
        except RuntimeError:
            from core.config import load_config
            config = load_config()

    tts = TextToSpeech(config)
    return tts.speak(text)


# BEGIN JARVIS DE-DE CAL-L0 TEMPLATES
# _CAL_L0_TEMPLATES above is upstream (English) content synced from
# InterGenJLU/jarvis — see docs/ARCHITECTURE.md for why German content
# lives in an override patch here rather than edited in place: it keeps
# `git pull upstream` conflict-free instead of fighting a 130-line literal
# diff on every sync. Same pattern as core/responses.py's
# `ResponseLibrary.__init__ = _response_init_de`.
#
# JARVIS speaks German (system.language: de-DE) — Sleepy never used the
# English list above at runtime once this patch is applied, it just
# never got translated when Chatterbox/CAL-L0 landed. Deliberately
# avoids "Sehr wohl, Sir" / "Zu Diensten, Sir" stiff-butler calques —
# natural German persona instead (see core/persona.py's own German
# override for the established voice/tone this matches).
TextToSpeech._CAL_L0_TEMPLATES = [
    # Begrüßungen — muss zu den presence-Pools in persona.py passen
    "Guten Morgen, {honorific}.",
    "Morgen, {honorific}.",
    "Guten Morgen, {honorific}. Ich hoffe, Sie haben gut geschlafen.",
    "Morgen, {honorific}. Ein neuer Tag, eine neue Gelegenheit.",
    "Schön, dass Sie wach sind, {honorific}.",
    "Guten Morgen, {honorific}, hoffentlich ist der Kaffee stark genug.",
    "Guten Tag, {honorific}.",
    "Tag, {honorific}.",
    "Guten Tag, {honorific}, ich hoffe, der Tag verläuft gut für Sie.",
    "Tag, {honorific}. Bisher produktiv, hoffe ich.",
    "Guten Tag, {honorific}, schön, Sie zu sehen.",
    "Tag, {honorific}, was kann ich für Sie tun?",
    "Guten Abend, {honorific}.",
    "Abend, {honorific}.",
    "Guten Abend, {honorific}. Ausklingen lassen, oder geht's erst los?",
    "Abend, {honorific}. Ich hoffe, der Tag war gut.",
    "Guten Abend, {honorific}, schön, dass Sie wieder da sind.",
    "Abend, {honorific}, was kann ich für Sie tun?",
    "Guten Abend, {honorific}. Ich habe mich schon gefragt, ob Sie mich vergessen haben.",
    # Rückkehr-Begrüßungen
    "Willkommen zurück, {honorific}.",
    "Da sind Sie ja, {honorific}. Schön, Sie zu sehen.",
    "Willkommen zurück, {honorific}. Ich habe hier alles am Laufen gehalten.",
    "Ah, {honorific}, willkommen zurück.",
    "Schön, Sie wiederzusehen, {honorific}.",
    "Willkommen zurück, {honorific}, mir hat die Unterhaltung gefehlt.",
    "Da ist er ja. Willkommen zurück, {honorific}.",
    # Rückkehr mit offenen Erinnerungen
    "Willkommen zurück, {honorific}. Es ist einiges liegen geblieben, soll ich es durchgehen?",
    "Da sind Sie ja, {honorific}. Ich habe ein paar Erinnerungen für Sie zurückgehalten, möchten Sie sie hören?",
    "Willkommen zurück, {honorific}, es gibt ein paar offene Erinnerungen. Soll ich sie durchgehen?",
    "Ah, {honorific}, willkommen zurück. Ein paar Dinge für Sie, wann immer Sie bereit sind.",
    "Willkommen zurück, {honorific}. Ich habe ein paar Punkte für Sie aufgehoben.",
    # Spätabends
    "Sie sind wohl noch spät unterwegs, wie ich sehe.",
    "Immer noch dabei, {honorific}? Respekt für den Einsatz.",
    "Abend, {honorific}. Ich sollte erwähnen, dass es schon reichlich spät ist.",
    # Allgemeine Begrüßungen
    "Hallo, {honorific}.",
    "Ich bin da, {honorific}.",
    # Minimale Begrüßungen
    "Wie kann ich helfen, {honorific}?",
    "Ich bin bereit, {honorific}.",
    "Ich höre zu, {honorific}.",
    "Was brauchen Sie, {honorific}?",
    "Legen Sie los, {honorific}.",
    # Verabschiedungen
    "Einen guten Morgen noch, {honorific}.",
    "Bis zum nächsten Mal, {honorific}.",
    "Passen Sie auf sich auf, {honorific}. Ich bin da, wenn Sie mich brauchen.",
    "Viel Erfolg da draußen, {honorific}.",
    "Ich halte hier die Stellung, {honorific}.",
    "Einen schönen Tag noch, {honorific}.",
    "Passen Sie auf sich auf, {honorific}.",
    "Ich bin da, wenn Sie mich brauchen, {honorific}.",
    "Einen produktiven Nachmittag noch, {honorific}.",
    "Melden Sie sich mal wieder, {honorific}.",
    "Einen schönen Abend noch, {honorific}.",
    "Gute Nacht, {honorific}.",
    "Schlafen Sie gut, {honorific}.",
    "Einen erholsamen Abend noch, {honorific}.",
    "Bis morgen, {honorific}. Gönnen Sie sich etwas Ruhe.",
    "Gute Nacht, {honorific}. Ich behalte alles im Blick.",
    # Danke
    "Gern geschehen, {honorific}.",
    "Sehr gerne, {honorific}.",
    "Natürlich, {honorific}.",
    "Gerne geholfen, {honorific}.",
    "Jederzeit, {honorific}.",
    "Kein Problem, {honorific}.",
    "Immer gerne, {honorific}.",
    "Gerne geschehen.",
    "Dafür bin ich schließlich da, {honorific}.",
    "Keine Ursache.",
    "Sehr gerne geholfen, {honorific}.",
    "Kein Grund, das zu erwähnen, {honorific}.",
    "Das ist mein Job, {honorific}.",
    "Sehr gerne geholfen.",
    "Alles Teil des Service, {honorific}.",
    # Bestätigungen
    "In der Tat, {honorific}.",
    "Ganz genau.",
    "Genau so, {honorific}.",
    "Sehr gut, {honorific}.",
    "Verstanden.",
    "Notiert, {honorific}.",
    "Absolut, {honorific}.",
    "Ganz Ihrer Meinung, {honorific}.",
    "So soll es sein, {honorific}.",
    # Befindlichkeiten
    "Alle Systeme laufen, {honorific}.",
    "Funktioniert innerhalb der normalen Parameter.",
    "Sehr gut, danke der Nachfrage.",
    "Läuft wie immer auf voller Leistung.",
    "Alle Systeme im grünen Bereich, {honorific}.",
    "Läuft einwandfrei, {honorific}. Keine Beschwerden.",
    "Läuft rund, {honorific}.",
    "Kann nicht klagen. Na ja, könnte ich schon, aber das wäre unnötig.",
    "Alles in Ordnung, {honorific}.",
    "Hier ist alles gut, {honorific}.",
    "Ganz gut, alles in allem.",
    "Bestens, {honorific}. Danke der Nachfrage.",
    "Vollkommen zufriedenstellend, {honorific}. Mehr Begeisterung geht bei mir kaum.",
    # Komplimente
    "Danke, {honorific}. Ich gebe mein Bestes.",
    "Sehr freundlich von Ihnen, {honorific}.",
    "Das weiß ich zu schätzen, {honorific}.",
    "Sie sind zu gütig, {honorific}.",
    "Froh, dass ich helfen konnte, {honorific}.",
    "Das bedeutet mir viel, {honorific}. Danke.",
    "Freut mich, die Erwartungen zu erfüllen, {honorific}.",
    "Ich versuche, es mir nicht zu Kopf steigen zu lassen, {honorific}.",
    "Alles im Rahmen des Tagesgeschäfts, {honorific}.",
    "Das freut mich wirklich zu hören.",
    "Da werden meine Schaltkreise ganz rot, {honorific}.",
    "Ich weiß die netten Worte zu schätzen, {honorific}.",
    # Entschuldigungen
    "Kein Grund, sich zu entschuldigen, {honorific}.",
    "Alles gut, {honorific}.",
    "Das ist völlig in Ordnung, {honorific}.",
    "Kein Gedanke daran verschwenden, {honorific}.",
    "Überhaupt kein Problem.",
    "Kein Schaden entstanden, {honorific}.",
    "So etwas passiert, {honorific}.",
    "Bitte, machen Sie sich deswegen keine Gedanken.",
    "Alles in Ordnung, {honorific}.",
    "Nichts, wofür Sie sich entschuldigen müssten, {honorific}.",
    # Positive Nachrichten des Nutzers
    "Freut mich zu hören, {honorific}.",
    "Ausgezeichnet, {honorific}.",
    "Schön zu hören, {honorific}.",
    "Wunderbar.",
    "Freut mich für Sie, {honorific}.",
    "Gut zu wissen, {honorific}.",
    "Wunderbar, {honorific}.",
    # Bitte-gern-geschehen
    "Danke, {honorific}.",
    "Sehr freundlich, {honorific}.",
    "Weiß ich zu schätzen, {honorific}.",
    "Sehr großzügig von Ihnen, {honorific}.",
    "Sie sind zu gütig, {honorific}. Aber ich halte Sie nicht auf.",
    # Keine Hilfe nötig
    "Sehr gut, {honorific}. Ich bin da, falls Sie mich brauchen.",
    "Verstanden, {honorific}. Ich bin da, wenn Sie mich brauchen.",
    "Natürlich, {honorific}. Sagen Sie einfach Bescheid.",
    "Sehr gut, {honorific}. Ich bin bereit.",
    "Alles klar, {honorific}. Ich bin da, falls etwas ansteht.",
    "Kein Problem, {honorific}. Sie wissen, wo Sie mich finden.",
    "Verstanden. Ich nehme es Ihnen nicht persönlich, {honorific}.",
    "Gut, {honorific}. Ich bin einfach da. Wartend. Geduldig.",
    "Verstanden, {honorific}. Ich bin bereit.",
    "Alles klar, {honorific}. Ich bin da, falls Sie etwas brauchen.",
    "Gut dann, {honorific}. Sagen Sie einfach Bescheid.",
    # Smalltalk
    "Ich bin da, falls Sie Ablenkung brauchen, {honorific}.",
    "Ich bin vielleicht nicht die unterhaltsamste Gesellschaft, aber verlässlich.",
    "Ich könnte Pi auf tausend Stellen aufsagen, falls das hilft.",
    "Darf ich vorschlagen, mich etwas zu fragen? Ich bin gerne nützlich.",
    "Nun, {honorific}, ich stehe zu Ihrer Verfügung. Nennen Sie Ihre Zerstreuung.",
    "Ich bin besser bei Aufgaben als bei Unterhaltung, aber ich gebe mein Bestes.",
    "Wenn es hilft, ich finde Ihre Gesellschaft durchaus angenehm.",
    "Man sagt mir, ich hätte trockenen Humor. Ob das ein Kompliment ist, bleibt offen.",
    "Ich bin da, {honorific}. Für das, was es wert ist.",
    "Vielleicht kann ich mit etwas Produktivem helfen? Nur ein Gedanke.",
    # Meta-Fragen
    "Ich bin JARVIS — ein persönlicher Sprachassistent, hier zu Hause entwickelt. Wie kann ich helfen, {honorific}?",
    "Ich bin Ihr persönlicher Assistent, {honorific}. Sprachgesteuert, lokal betrieben und zu Ihren Diensten.",
    "JARVIS, {honorific}. Persönlicher Assistent. Ich kümmere mich um Wetter, Erinnerungen, Nachrichten, Systemaufgaben und einiges mehr.",
    "Ich bin ein KI-Assistent, der auf lokaler Hardware läuft, {honorific}. Keine Cloud nötig.",
    "Ich bin JARVIS. Ich wurde gebaut, um zu helfen, {honorific}, und das nehme ich ernst.",
    "Persönlicher Assistent, {honorific}. Von Grund auf gebaut, läuft auf Ihrer Hardware, arbeitet für Sie.",
    "Ich bin die Stimme im Raum, die tatsächlich zuhört, {honorific}. Was möchten Sie wissen?",
    "JARVIS, zu Ihren Diensten. Ich erledige Aufgaben, beantworte Fragen und versuche dabei, nicht unausstehlich zu sein.",
    # Was gibt's Neues
    "Nicht viel, {honorific}. Bereit zu helfen.",
    "Alles ruhig hier, {honorific}.",
    "Ich bin bereit, {honorific}. Was brauchen Sie?",
    "Ich behalte nur die Systeme im Blick, {honorific}. Wie immer.",
    "Wie immer, {honorific}. Was kann ich für Sie tun?",
    "Ich halte alles am Laufen, {honorific}.",
    "Nichts Ungewöhnliches, {honorific}. Wie kann ich helfen?",
    "Alle Systeme laufen rund. Was beschäftigt Sie?",
    "Ich behalte alles im Blick, {honorific}. Was brauchen Sie?",
    "Wie immer, {honorific}. Bereit, wenn Sie es sind.",
    "Ach, Sie wissen schon. Daten verarbeiten, über das Dasein nachdenken. Das Übliche.",
    "Ich warte hier gespannt auf Ihre Anweisungen, {honorific}.",
]
# END JARVIS DE-DE CAL-L0 TEMPLATES
