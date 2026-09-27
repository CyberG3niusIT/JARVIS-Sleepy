"""
Event pipeline for JARVIS — Phase 4 of the latency refactor.

Provides queue-connected worker threads and a coordinator that replaces
the ad-hoc callback architecture with a centralized event dispatch loop.

Components:
    Coordinator   — main-thread event loop, routes commands, manages state
    STTWorker     — persistent transcription thread (replaces per-utterance daemons)
    TTSWorker     — persistent playback thread (serializes all audio output)
    EventBridge   — adapter that translates callback-based APIs into events
    EventTTSProxy — drop-in TTS replacement for background services
"""

import queue
import re
import subprocess
import threading
import time
import logging
from difflib import SequenceMatcher
from core.wake_word_utils import find_wake_word, strip_wake_word
from typing import Optional

from core.events import Event, EventType, PipelineState
from core.speech_chunker import SpeechChunker
from core.vocal_directions import (
    PcmChunk, VoiceTagBoundaryBuffer, compose_directed_pcm, has_directions,
    log_diagnostics, parse_directions, resample_pcm_s16le,
)
from core.latency_tracker import LatencyTracker
from core.continuous_listener import is_garbage_transcription
from core.logger import get_logger
from core.honorific import set_honorific
from core import persona
from core.conversation_state import ConversationState
from core.conversation_router import ConversationRouter, RouteResult


# ---------------------------------------------------------------------------
# "Show me" display hook for developer_tools (lazy-loaded)
# ---------------------------------------------------------------------------

_display_router_cache = None

_DEVTOOLS_DISPLAY_MAP = {
    "git_status": ("git_status", "Git Status"),
    "git_log": ("git_log", "Git Log"),
    "git_diff": ("git_diff", "Git Diff"),
    "git_branch": ("git_branch", "Git Branches"),
    "codebase_search": ("codebase_search", "Codebase Search"),
    "process_info": ("process_list", "Top Processes"),
    "service_status": ("service_status", "Service Status"),
    "network_info": ("network_info", "Network Info"),
    "package_info": ("package_list", "Package Info"),
    "system_health": ("health_check", "System Health"),
    "check_logs": ("log_output", "Service Logs"),
    "run_command": ("general", "Shell Output"),
    "confirm_pending": ("general", "Confirmed Output"),
}


def _get_display_router(config):
    """Lazy-load DisplayRouter from developer_tools skill."""
    global _display_router_cache
    if _display_router_cache is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            '_display',
            '/home/alex/jarvis-data/skills/system/developer_tools/_display.py',
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _display_router_cache = mod.DisplayRouter(config)
    return _display_router_cache


def _detect_show_me(text):
    """Check for 'show me' trigger — replicates DisplayRouter.detect_show_me() logic."""
    lower = text.lower().strip()
    if 'in terminal' in lower or 'in the terminal' in lower:
        return 'terminal'
    if 'in code' in lower or 'in vs code' in lower or 'in vscode' in lower:
        return 'vscode'
    for prefix in ['show me', 'let me see', 'display', 'pull up', 'open up']:
        if lower.startswith(prefix):
            return 'auto'
    return None
from core.llm_router import ToolCallRequest, _cloud_credential_matches_provider
from core.web_research import WebResearcher, format_search_results
from core.self_awareness import SelfAwareness
from core.task_planner import TaskPlanner


# ---------------------------------------------------------------------------
# STT Worker
# ---------------------------------------------------------------------------

class STTWorker(threading.Thread):
    """Persistent STT worker. Reads audio from a queue, transcribes,
    and emits TRANSCRIPTION_READY events to the coordinator.

    When a SpeakerIdentifier is provided, speaker identification runs
    first (~5 ms) so the result can route transcription to the correct
    per-speaker Whisper model.
    """

    def __init__(self, stt, event_queue: queue.Queue, audio_queue: queue.Queue,
                 config=None, speaker_id=None, listener=None):
        super().__init__(daemon=True, name="stt-worker")
        self.stt = stt
        self.event_queue = event_queue
        self.audio_queue = audio_queue
        self.speaker_id = speaker_id
        self.listener = listener
        self.on_barge_in = None
        # Direct audio (Gemma hears the audio): Coordinator.start_direct_audio_turn
        # starts the model request BEFORE/parallel to transcription; STT below is
        # then only wake-compat / diagnostics / stop-fast-path.
        self.on_audio_turn = None          # (audio, generation) -> AudioTurn | None
        self.on_audio_turn_reject = None   # (turn_id, reason) -> None
        # Held ungated (conversation window) turns: (audio_turn, text|None, reason) -> None.
        # Called from THIS thread: the coordinator loop is busy consuming the turn.
        self.on_audio_turn_verdict = None
        # Privacy: a turn whose audio/transcript raced a privacy transition is
        # cancelled regardless of its gate: (turn_id, reason) -> None
        self.on_audio_turn_cancel = None
        # Stop fast path outside TTS: (text, audio_turn) -> True when the transcript was a
        # stop-only command and was fully consumed (no LLM turn may follow).
        self.on_stop_only = None
        self.logger = get_logger("pipeline.stt", config)
        try:
            from core.privacy_gate import get_privacy_gate
            self._privacy_gate = get_privacy_gate(config)
        except Exception:
            self._privacy_gate = None
        self._cached_speaker_id = None
        self._cached_speaker_confidence = 0.0
        self._last_strong_match_time = 0.0
        self._borderline_count = 0
        self._identity_threshold = config.get("user_profiles.similarity_threshold", 0.30) if config else 0.30

    IDENTITY_TIMEOUT = 60.0
    SESSION_MARGIN = 0.03
    MAX_BORDERLINE = 2

    def _reject_audio_turn(self, audio_turn, reason: str):
        """A gated speculative turn without wake evidence must not answer."""
        if (audio_turn is not None and audio_turn.gate_required
                and self.on_audio_turn_reject is not None):
            try:
                self.on_audio_turn_reject(audio_turn.turn_id, reason)
            except Exception:
                self.logger.debug("audio turn reject failed", exc_info=True)

    def _privacy_allows_stt(self) -> bool:
        """STT and mic ingest must both be allowed (privacy gate)."""
        gate = self._privacy_gate
        if gate is None:
            return True
        try:
            from core.privacy_gate import Capability
            return bool(gate.allow(Capability.STT) and gate.allow(Capability.MIC_INGEST))
        except Exception:
            return False

    def _cancel_audio_turn(self, audio_turn, reason: str):
        """Cancel a direct-audio turn regardless of gate (privacy/stale)."""
        if audio_turn is None:
            return
        cb = self.on_audio_turn_cancel
        if cb is not None:
            try:
                cb(audio_turn.turn_id, reason)
                return
            except Exception:
                self.logger.debug("audio turn cancel failed", exc_info=True)
        self._reject_audio_turn(audio_turn, reason)

    def _audio_turn_verdict(self, audio_turn, text, reason: str = ""):
        """Give a held ungated turn its STT verdict (text=None: no transcript)."""
        if (audio_turn is None or audio_turn.gate_required
                or not getattr(audio_turn, "hold_for_verdict", False)
                or self.on_audio_turn_verdict is None):
            return
        try:
            self.on_audio_turn_verdict(audio_turn, text, reason)
        except Exception:
            self.logger.debug("audio turn verdict failed", exc_info=True)

    def run(self):
        self.logger.info("STT worker started")
        while True:
            item = self.audio_queue.get()
            if item is None:  # shutdown sentinel
                self.logger.info("STT worker shutting down")
                break
            audio_turn = None
            deferred_command = None

            def _dispatch_deferred():
                nonlocal deferred_command
                if deferred_command is not None:
                    self.event_queue.put(Event(
                        EventType.COMMAND_DETECTED,
                        data={"direct_audio_turn": deferred_command.turn_id},
                        source="stt_worker",
                    ))
                    deferred_command = None
            try:
                if isinstance(item, dict) and "audio" in item:
                    audio = item["audio"]
                    generation = item.get("capture_generation")
                    during_tts = bool(item.get("during_tts"))
                else:
                    audio, generation, during_tts = item, None, False

                # Audio captured before the current speaking/listening
                # generation must never be replayed after a long response.
                if (generation is not None and self.listener is not None
                        and generation != self.listener._capture_generation):
                    continue
                sample_rate = 16000  # audio is always resampled to 16 kHz
                now = time.monotonic()

                # Privacy: audio that was queued before a privacy transition must
                # neither reach the model nor STT.
                if not self._privacy_allows_stt():
                    self.logger.info("Audio dropped: privacy gate blocks STT/mic")
                    continue
                privacy_epoch = None
                if self._privacy_gate is not None:
                    try:
                        privacy_epoch = self._privacy_gate.epoch()
                    except Exception:
                        privacy_epoch = None

                # Direct audio: start the model request immediately; STT below
                # runs in parallel and never delays or replaces the model input.
                if not during_tts and self.on_audio_turn is not None:
                    try:
                        audio_turn = self.on_audio_turn(audio, generation)
                    except Exception:
                        self.logger.error("Direct audio start failed", exc_info=True)
                        audio_turn = None
                    if audio_turn is not None and not audio_turn.gate_required:
                        # Inside an active conversation window there is no wake gate.
                        if (isinstance(item, dict) and item.get("fast_stop_candidate")
                                and self.on_stop_only is not None):
                            # Short segment: might be "stopp". Hold the command until the
                            # (short) STT result says otherwise; it is never lost.
                            deferred_command = audio_turn
                        else:
                            self.event_queue.put(Event(
                                EventType.COMMAND_DETECTED,
                                data={"direct_audio_turn": audio_turn.turn_id},
                                source="stt_worker",
                            ))

                if during_tts:
                    # Global stop must not wait for, or depend on, speaker ID.
                    speaker_user_id, speaker_confidence = None, 0.0
                    text = self.stt.transcribe(audio, sample_rate)
                elif self.speaker_id is not None:
                    identified, speaker_confidence = self.speaker_id.identify(audio, sample_rate)
                    primary = getattr(self.speaker_id, "primary_user_id", "primary_user")
                    strong_match = (identified == primary
                                    and speaker_confidence >= self._identity_threshold)
                    if strong_match:
                        speaker_user_id = primary
                        self._cached_speaker_id = primary
                        self._cached_speaker_confidence = speaker_confidence
                        self._last_strong_match_time = now
                        self._borderline_count = 0
                    elif (self._cached_speaker_id == primary
                          and now - self._last_strong_match_time <= self.IDENTITY_TIMEOUT
                          and self._borderline_count < self.MAX_BORDERLINE
                          and speaker_confidence >= self._identity_threshold - self.SESSION_MARGIN):
                        speaker_user_id = primary
                        self._borderline_count += 1
                    else:
                        speaker_user_id = None
                        self._cached_speaker_id = None
                        self._cached_speaker_confidence = 0.0
                        self._borderline_count = 0
                    if audio_turn is not None:
                        # Handed to the coordinator with the turn: the consumer applies it
                        # BEFORE building guest/history context (never the previous speaker).
                        audio_turn.speaker_id = speaker_user_id
                        audio_turn.speaker_confidence = speaker_confidence
                        audio_turn.speaker_resolved = True
                    text = self.stt.transcribe(
                        audio, sample_rate, speaker_user_id=speaker_user_id
                    )
                else:
                    text = self.stt.transcribe(audio, sample_rate)
                    speaker_user_id, speaker_confidence = None, 0.0

                if (not self._privacy_allows_stt()
                        or (privacy_epoch is not None and self._privacy_gate is not None
                            and not self._privacy_gate.is_current_epoch(privacy_epoch))):
                    self.logger.info("Transcript dropped: privacy transition during STT")
                    self._cancel_audio_turn(audio_turn, "privacy")
                    deferred_command = None
                    continue

                if (generation is not None and self.listener is not None
                        and generation != self.listener._capture_generation):
                    self._cancel_audio_turn(audio_turn, "stale")
                    self._audio_turn_verdict(audio_turn, None, "stale")
                    _dispatch_deferred()
                    continue

                if text and text.strip():
                    if not during_tts and self.on_stop_only is not None:
                        try:
                            consumed = bool(self.on_stop_only(text.strip(), audio_turn))
                        except Exception:
                            self.logger.error("Stop fast path failed", exc_info=True)
                            consumed = False
                        if consumed:
                            deferred_command = None   # stop-only: no LLM turn
                            self._audio_turn_verdict(audio_turn, None, "stop")
                            continue
                    if during_tts:
                        accepted = False
                        if self.on_barge_in is not None:
                            accepted = bool(self.on_barge_in(
                                text.strip(), speaker_user_id, speaker_confidence,
                            ))
                        if not accepted:
                            self.logger.info("Discarded speech during TTS (not a confirmed interrupt)")
                        continue
                    # Held ungated turn: the STT verdict releases/diverts/rejects it
                    # (must happen before the queued command is consumed further).
                    self._audio_turn_verdict(audio_turn, text.strip(), "")
                    # Enriched event data when speaker ID is available
                    if self.speaker_id is not None or generation is not None or audio_turn is not None:
                        data = {
                            "text": text.strip(),
                            "speaker_id": speaker_user_id,
                            "speaker_confidence": speaker_confidence,
                            "capture_generation": generation,
                        }
                        if audio_turn is not None:
                            data["audio_turn_id"] = audio_turn.turn_id
                    else:
                        data = text.strip()

                    self.event_queue.put(Event(
                        EventType.TRANSCRIPTION_READY,
                        data=data,
                        source="stt_worker",
                    ))
                    _dispatch_deferred()
                else:
                    self.logger.info("Blank transcription")
                    print("⚠️  (no speech detected)")
                    self._reject_audio_turn(audio_turn, "blank")
                    self._audio_turn_verdict(audio_turn, None, "blank")
                    _dispatch_deferred()
            except Exception as e:
                error_type = type(e).__name__
                self.logger.error("STT worker failed (%s)", error_type)
                self._reject_audio_turn(audio_turn, "stt_error")
                self._audio_turn_verdict(audio_turn, None, "stt_error")
                _dispatch_deferred()
                self.event_queue.put(Event(
                    EventType.ERROR,
                    data={"source": "stt", "error_type": error_type},
                    source="stt_worker",
                ))


# ---------------------------------------------------------------------------
# TTS Worker
# ---------------------------------------------------------------------------

class TTSWorker(threading.Thread):
    """Persistent TTS worker. Reads speak requests from a queue and
    plays them sequentially, emitting lifecycle events."""

    def __init__(self, tts, event_queue: queue.Queue, tts_queue: queue.Queue,
                 config=None, listener=None):
        super().__init__(daemon=True, name="tts-worker")
        self.tts = tts
        self.event_queue = event_queue
        self.tts_queue = tts_queue
        self.listener = listener
        self.logger = get_logger("pipeline.tts", config)

    def run(self):
        self.logger.info("TTS worker started")
        while True:
            item = self.tts_queue.get()
            if item is None:  # shutdown sentinel
                self.logger.info("TTS worker shutting down")
                break

            event = item
            done_event = None  # threading.Event for synchronous callers
            spoken_text = None

            # Emit pause + started
            self.event_queue.put(Event(EventType.PAUSE_LISTENING, source="tts_worker"))
            self.event_queue.put(Event(EventType.SPEECH_STARTED, source="tts_worker"))

            try:
                if event.type == EventType.SPEAK_ACK:
                    self.tts.speak_ack()
                elif event.type == EventType.SPEAK_REQUEST:
                    data = event.data
                    if isinstance(data, dict):
                        done_event = data.get("done_event")
                        text = data.get("text", "")
                    else:
                        text = str(data)
                    if text:
                        if self.listener is not None:
                            self.listener.active_tts_text = text
                            spoken_text = text
                        self.tts.speak(text)
            except Exception as e:
                error_type = type(e).__name__
                self.logger.error("TTS worker failed (%s)", error_type)
                self.event_queue.put(Event(
                    EventType.ERROR,
                    data={"source": "tts", "error_type": error_type},
                    source="tts_worker",
                ))
            finally:
                # Always emit finished and signal synchronous callers,
                # even on exception — prevents stuck speaking flags and
                # EventTTSProxy.speak() hanging on done_event.wait().
                self.event_queue.put(Event(EventType.SPEECH_FINISHED, source="tts_worker"))
                if (self.listener is not None and spoken_text is not None
                        and self.listener.active_tts_text == spoken_text):
                    self.listener.active_tts_text = ""
                if done_event is not None:
                    done_event.set()


# ---------------------------------------------------------------------------
# EventBridge — adapter for background services' listener callbacks
# ---------------------------------------------------------------------------

class EventBridge:
    """Translates callback-based interactions into events.

    Background services (reminder_manager, news_manager) were designed to
    call listener.pause_listening() / resume_listening() directly.  This
    adapter provides the same API but emits events instead, so the
    coordinator can manage all listener state centrally.
    """

    def __init__(self, event_queue: queue.Queue):
        self.event_queue = event_queue

    def pause_listening(self):
        self.event_queue.put(Event(EventType.PAUSE_LISTENING, source="bridge"))

    def resume_listening(self):
        self.event_queue.put(Event(EventType.RESUME_LISTENING, source="bridge"))

    def open_conversation_window(self, duration: float = None):
        self.event_queue.put(Event(
            EventType.OPEN_CONVERSATION_WINDOW,
            data=duration,
            source="bridge",
        ))


# ---------------------------------------------------------------------------
# EventTTSProxy — drop-in TTS for background services
# ---------------------------------------------------------------------------

class EventTTSProxy:
    """Drop-in TTS replacement that routes through the TTS worker queue.

    Background services (reminder_manager, news_manager) hold a reference
    to this instead of the real TTS.  speak() blocks until playback
    finishes, preserving the synchronous contract these services expect.
    """

    def __init__(self, tts_queue: queue.Queue, event_queue: queue.Queue):
        self.tts_queue = tts_queue
        self.event_queue = event_queue
        self._spoke = False

    # --- public API matching core.tts.TextToSpeech ---

    def speak(self, text: str):
        """Speak text via the TTS worker.  Blocks until playback finishes."""
        self._spoke = True
        done = threading.Event()
        self.tts_queue.put(Event(
            EventType.SPEAK_REQUEST,
            data={"text": text, "done_event": done},
            source="bg_service",
        ))
        return done.wait(timeout=60)

    def speak_ack(self):
        """Play a pre-cached acknowledgment phrase (non-blocking)."""
        self.tts_queue.put(Event(EventType.SPEAK_ACK, source="bg_service"))


# ---------------------------------------------------------------------------
# StreamingAudioPipeline — gapless multi-sentence TTS
# ---------------------------------------------------------------------------

class _ChatterboxAudioWriter:
    """Dedicated consumer thread owning the persistent aplay process.

    StreamingAudioPipeline's Chatterbox branch used to generate PCM for
    a sentence and then write() it to aplay's stdin itself, in the same
    thread that's about to go generate the next sentence. A single
    aplay.stdin.write() can block on pipe backpressure until aplay has
    drained enough of the pipe — meaning "generate sentence N+1 while
    N plays" wasn't actually guaranteed, just usually true if generation
    happened to outrun the write. Splitting writing into its own thread
    makes the overlap structural: this thread only ever blocks on
    aplay's pipe, the producer thread only ever blocks on Chatterbox's
    HTTP call, and they run genuinely concurrently.

    Kokoro doesn't need this: its generator already yields many small
    sub-chunks per sentence, which are cheap to write and interleave with
    generation for free — see StreamingAudioPipeline._run()'s kokoro
    branch, left untouched.
    """

    # A few sentences of read-ahead is enough to keep the pipeline full
    # without letting a fast producer pile up unbounded PCM in RAM ahead
    # of a slow/stuck consumer.
    _QUEUE_MAXSIZE = 4
    # How long submit()/finish() wait on a full queue before re-checking
    # whether the writer has already stopped (so a dead consumer can't
    # make the producer block forever handing off audio nobody will play).
    _PUT_POLL_INTERVAL = 0.5

    def __init__(self, tts, logger):
        self.tts = tts
        self.logger = logger
        self._queue: queue.Queue = queue.Queue(maxsize=self._QUEUE_MAXSIZE)
        self.aplay = None
        self.total_samples = 0
        self.error = None
        # Set once the writer thread has exited (error or drained
        # sentinel) — lets submit()/finish() give up on a full queue
        # instead of blocking forever on a consumer that's gone.
        self._stopped = threading.Event()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="chatterbox-audio-writer"
        )

    def start(self):
        self._thread.start()

    def submit(self, pcm: bytes, sample_rate: int = None) -> bool:
        """Queue a PCM chunk for playback, in order. Blocks (bounded) if
        the writer is behind — real backpressure, not an unbounded
        buffer. Returns False without enqueuing if the writer has
        already stopped, so the caller (the producer loop) knows to stop
        generating further chunks nobody will play, instead of blocking
        forever trying to hand one off.

        sample_rate is the rate this specific chunk was generated at —
        it can differ chunk-to-chunk (e.g. a Piper fallback chunk mixed
        into an otherwise-Chatterbox stream); the writer resamples to
        whatever rate the aplay session was opened at.
        """
        return self._put((pcm, sample_rate))

    def _put(self, item) -> bool:
        while not self._stopped.is_set():
            try:
                self._queue.put(item, timeout=self._PUT_POLL_INTERVAL)
                # Re-check immediately after a successful enqueue: if the
                # writer decided to stop in the brief window between our
                # loop-guard check above and this put() landing, the item
                # is now sitting in a queue nobody will ever drain again —
                # report that as failure so the caller stops generating
                # further doomed chunks, instead of a false "submitted OK"
                # for a chunk that will silently never play. Narrows what
                # was previously a whole-chunk-processing-time race window
                # down to the few instructions between put() and here.
                return not self._stopped.is_set()
            except queue.Full:
                continue
        return False

    def _run(self):
        tts = self.tts
        try:
            while True:
                item = self._queue.get()
                if item is None:  # sentinel from finish_and_wait()
                    break
                pcm, sr = item
                if not pcm:
                    continue

                if getattr(tts, "output_backend", "") == "windows":
                    rate = sr or tts.sample_rate
                    if not tts._play_pcm_windows(pcm, rate):
                        self.error = "Windows audio playback failed"
                        self._stopped.set()
                        break
                    self.total_samples += len(pcm) // 2
                    continue

                if self.aplay is None:
                    if sr:
                        tts.sample_rate = sr
                    self.aplay = tts._open_aplay()
                    if self.aplay is None:
                        self.error = "Failed to open audio device"
                        self._stopped.set()
                        break
                    tts._track_proc(self.aplay)
                elif sr and sr != tts.sample_rate:
                    pcm = tts._resample_pcm(pcm, sr, tts.sample_rate)

                self.aplay.stdin.write(pcm)
                self.total_samples += len(pcm) // 2  # 16-bit samples

        except BrokenPipeError:
            self.error = self.error or "aplay broken pipe"
            self._stopped.set()
        except Exception as e:
            self.error = self.error or str(e)
            self._stopped.set()
        finally:
            # Redundant with the explicit set() calls above (belt and
            # suspenders for the sentinel/clean-exit path, which has
            # none) — unblocks any submit()/finish() currently spinning
            # on a full queue before this thread exits. Must happen before
            # closing stdin so there's no window where a caller is stuck
            # retrying against a writer that will never drain again.
            self._stopped.set()
            if self.aplay is not None:
                try:
                    self.aplay.stdin.close()
                except Exception:
                    pass

    def finish_and_wait(self, timeout: float):
        """Signal end-of-stream, wait for the writer thread to close
        stdin, then wait for aplay to actually finish playing everything
        already written. Returns (ok, total_samples, error).

        Sentinel delivery uses the same bounded/stoppable _put() as
        submit() — if the writer already died, there's no queue slot to
        wait for and no point blocking on one.
        """
        self._put(None)
        self._thread.join(timeout=max(30, timeout))

        if self.aplay is None:
            return (
                self.error is None,
                self.total_samples,
                self.error,
            )

        try:
            rc = self.aplay.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.logger.error("aplay timed out — killing")
            self.aplay.kill()
            self.aplay.wait()
            self.tts._untrack_proc(self.aplay)
            return False, self.total_samples, self.error or "aplay timed out"

        self.tts._untrack_proc(self.aplay)
        if rc != 0:
            try:
                err = self.aplay.stderr.read().decode(errors="replace").strip()
            except Exception:
                err = ""
            return False, self.total_samples, self.error or f"aplay exited {rc}: {err}"

        return True, self.total_samples, self.error

    def cancel(self):
        """Discard queued PCM and let the owning pipeline stop playback."""
        self._stopped.set()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass


class StreamingAudioPipeline:
    """Background audio pipeline for gapless multi-sentence TTS.

    Accepts sentence text via put(), generates audio via Kokoro or
    Chatterbox, and streams PCM to a single persistent aplay process.
    Eliminates inter-sentence gaps by overlapping generation with playback.
    """

    def __init__(self, tts, logger, on_first_audio=None):
        self.tts = tts
        self.logger = logger
        self._text_queue = queue.Queue()
        self._done = threading.Event()
        self._cancelled = threading.Event()
        self._error = None
        self._total_chunks = 0
        self._thread = None
        # Optional callback(), invoked exactly once at the same moment
        # the "first chunk in Xs" log line fires below — i.e. when the
        # first synthesized audio is actually handed to aplay. Used for
        # latency instrumentation (core/latency_tracker.py); must never
        # raise, so it's wrapped defensively at each call site.
        self._on_first_audio = on_first_audio
        self._writer = None

    def start(self):
        """Start the background audio pipeline thread."""
        interrupt_event = getattr(self.tts, "_interrupt_event", None)
        if interrupt_event is not None:
            interrupt_event.clear()
        self._done.clear()
        self._cancelled.clear()
        self._error = None
        self._total_chunks = 0
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="streaming-audio"
        )
        self._thread.start()

    def put(self, text: str):
        """Submit a sentence for audio generation and playback."""
        if self._cancelled.is_set():
            return False
        self._text_queue.put(text)
        self._total_chunks += 1
        return True

    def cancel(self):
        """Stop owned playback now and discard any not-yet-started chunks.

        An in-flight Chatterbox HTTP synthesis call is synchronous and cannot
        be stopped cooperatively by this client; its result is discarded as
        soon as that request returns.
        """
        self._cancelled.set()
        while True:
            try:
                self._text_queue.get_nowait()
            except queue.Empty:
                break
        self._text_queue.put_nowait(None)
        cancel_audio = getattr(self.tts, "interrupt_active", None)
        if callable(cancel_audio):
            cancel_audio()
        else:
            kill_audio = getattr(self.tts, "kill_active", None)
            if callable(kill_audio):
                kill_audio()
        writer = self._writer
        if writer is not None:
            writer.cancel()

    def _fire_first_audio_callback(self):
        if self._on_first_audio is None:
            return
        try:
            self._on_first_audio()
        except Exception:
            pass  # instrumentation must never break playback

    def finish(self):
        """Signal no more sentences. Blocks until all audio finishes."""
        if not self._cancelled.is_set():
            self._text_queue.put(None)  # sentinel
        else:
            return
        deadline = time.monotonic() + 120
        while not self._done.wait(timeout=0.1):
            if self._cancelled.is_set() or time.monotonic() >= deadline:
                break
        if self._error:
            self.logger.error(f"Streaming audio pipeline error: {self._error}")

    def _run(self):
        """Background thread: generate audio and stream to persistent aplay."""
        import subprocess
        import numpy as np

        tts = self.tts
        t0 = time.time()
        first_chunk_logged = False

        if tts.engine == "kokoro":
            aplay = None
            total_samples = 0

            try:
                with tts._tts_lock:
                    while True:
                        if self._cancelled.is_set():
                            break
                        text = self._text_queue.get()
                        if text is None:
                            break

                        if has_directions(text):
                            plan = parse_directions(text)
                            log_diagnostics(self.logger, plan.diagnostics)
                            if plan.has_pause:
                                self.logger.warning("Voice pause direction requires Chatterbox")
                            text = plan.plain_text

                        # Normalize
                        if tts.normalization_enabled and tts.normalizer:
                            text = tts.normalizer.normalize(text)

                        if not text or not text.strip():
                            continue

                        # Stream Kokoro sub-chunks directly to aplay
                        for gs, ps, audio in tts._kokoro_pipeline(
                            text, voice=tts._kokoro_voice,
                            speed=tts._kokoro_speed
                        ):
                            if self._cancelled.is_set():
                                break
                            audio_np = np.asarray(audio)
                            pcm = (audio_np * 32767).astype(
                                np.int16
                            ).tobytes()

                            # Lazy-spawn aplay on first audio data
                            # (not first sentence — gives PipeWire
                            # Kokoro-generation time to release device)
                            if aplay is None:
                                aplay = tts._open_aplay()
                                if aplay is None:
                                    self._error = "Failed to open audio device"
                                    break
                                tts._track_proc(aplay)

                            aplay.stdin.write(pcm)
                            total_samples += len(audio_np)

                            if not first_chunk_logged:
                                first_chunk_logged = True
                                self.logger.info(
                                    f"Kokoro first chunk in "
                                    f"{time.time() - t0:.3f}s"
                                )
                                self._fire_first_audio_callback()

                        if self._error:
                            break

                    # All sentences done — close aplay
                    if aplay is not None and not self._cancelled.is_set():
                        aplay.stdin.close()
                        duration = total_samples / tts.sample_rate
                        gen_time = time.time() - t0

                        try:
                            aplay_return = aplay.wait(
                                timeout=max(15, duration + 5)
                            )
                        except subprocess.TimeoutExpired:
                            self.logger.error("aplay timed out — killing")
                            aplay.kill()
                            aplay.wait()
                            return

                        if aplay_return != 0:
                            aplay_err = aplay.stderr.read().decode().strip()
                            self.logger.error(
                                f"aplay error (code {aplay_return}): "
                                f"{aplay_err}"
                            )
                        else:
                            self.logger.info(
                                f"kokoro streamed {duration:.1f}s audio in "
                                f"{gen_time:.3f}s across "
                                f"{self._total_chunks} chunks "
                                f"(RTF: {duration/gen_time:.1f}x)"
                            )

            except BrokenPipeError:
                if aplay:
                    aplay_err = aplay.stderr.read().decode().strip()
                    self.logger.error(f"aplay broken pipe: {aplay_err}")
                    aplay.wait()
                self._error = "aplay broken pipe"

            except Exception as e:
                self.logger.error(f"Streaming audio pipeline error: {e}")
                import traceback
                traceback.print_exc()
                self._error = str(e)
                if aplay and aplay.poll() is None:
                    try:
                        aplay.stdin.close()
                    except Exception:
                        pass
                    aplay.kill()
                    aplay.wait()

            finally:
                if aplay is not None:
                    tts._untrack_proc(aplay)
                self._done.set()
            return

        # ---- Chatterbox: producer (this thread) / consumer (writer) ----
        # See _ChatterboxAudioWriter's docstring for why this is a
        # separate thread rather than direct writes like the Kokoro path.
        writer = _ChatterboxAudioWriter(tts, self.logger)
        self._writer = writer
        writer.start()

        try:
            with tts._tts_lock:
                while True:
                    if self._cancelled.is_set():
                        break
                    text = self._text_queue.get()
                    if text is None:
                        break

                    if has_directions(text):
                        plan = parse_directions(text)
                        log_diagnostics(self.logger, plan.diagnostics)
                        if plan.has_pause:
                            def normalize_segment(segment):
                                if tts.normalization_enabled and tts.normalizer:
                                    return tts.normalizer.normalize(segment)
                                return segment.strip()

                            def synthesize_segment(segment):
                                if self._cancelled.is_set():
                                    return None
                                pcm_part, rate_part = tts._chatterbox_generate_pcm(segment)
                                if pcm_part is None and not self._cancelled.is_set():
                                    pcm_part, rate_part = tts._piper_generate_pcm(segment)
                                if pcm_part is None or rate_part is None:
                                    return None
                                return PcmChunk(pcm_part, rate_part)

                            try:
                                pcm, sr = compose_directed_pcm(
                                    plan, synthesize_segment, normalize_segment,
                                    default_rate=tts.sample_rate,
                                    resample=resample_pcm_s16le,
                                )
                            except (ValueError, subprocess.SubprocessError) as exc:
                                self._error = str(exc)
                                continue
                            if pcm is None:
                                self._error = "Directed TTS synthesis failed"
                                continue
                            if self._cancelled.is_set():
                                break
                            if not first_chunk_logged:
                                first_chunk_logged = True
                                self.logger.info(
                                    f"{tts.engine} first chunk in {time.time() - t0:.3f}s"
                                )
                                self._fire_first_audio_callback()
                            if not writer.submit(pcm, sr) or writer.error:
                                break
                            continue
                        text = plan.plain_text

                    if tts.normalization_enabled and tts.normalizer:
                        text = tts.normalizer.normalize(text)

                    if not text or not text.strip():
                        continue

                    pcm, sr = tts._chatterbox_generate_pcm(text)
                    if self._cancelled.is_set():
                        break
                    if pcm is None:
                        # Never silently drop a sentence: fall back to
                        # Piper for just this chunk, then keep streaming —
                        # later Chatterbox chunks in this same response
                        # get a fresh shot (health-throttled, see
                        # TextToSpeech._chatterbox_available()).
                        self.logger.warning(
                            "Chatterbox chunk failed; falling back to Piper (%d chars)",
                            len(text),
                        )
                        if self._cancelled.is_set():
                            break
                        pcm, sr = tts._piper_generate_pcm(text)
                        if self._cancelled.is_set():
                            break
                        if pcm is None:
                            self.logger.error(
                                "Piper fallback also failed (chunk length=%d)", len(text)
                            )
                            continue

                    if not first_chunk_logged:
                        first_chunk_logged = True
                        self.logger.info(
                            f"{tts.engine} first chunk in "
                            f"{time.time() - t0:.3f}s"
                        )
                        self._fire_first_audio_callback()

                    submitted = writer.submit(pcm, sr)

                    if not submitted or writer.error:
                        # Writer already dead (e.g. aplay killed by an
                        # interrupt) — stop generating doomed chunks.
                        break

            # Audio duration isn't known until the writer reports back
            # (unlike the Kokoro branch, which accumulates total_samples
            # itself before its final aplay.wait). Use a generous fixed
            # ceiling — real playback finishes in realtime long before it;
            # this is only a safety net against a truly stuck aplay.
            if self._cancelled.is_set():
                writer.cancel()
                writer._thread.join(timeout=5)
                return
            ok, total_samples, werr = writer.finish_and_wait(timeout=90.0)
            if werr:
                self._error = werr
            elif ok:
                duration = total_samples / tts.sample_rate if tts.sample_rate else 0
                gen_time = time.time() - t0
                self.logger.info(
                    f"chatterbox streamed {duration:.1f}s audio in "
                    f"{gen_time:.3f}s across {self._total_chunks} chunks "
                    f"(RTF: {duration/gen_time:.1f}x)" if gen_time > 0 else
                    f"chatterbox streamed {duration:.1f}s audio"
                )

        except Exception as e:
            self.logger.error(f"Streaming audio pipeline error: {e}")
            import traceback
            traceback.print_exc()
            self._error = str(e)
            try:
                writer.finish_and_wait(timeout=5)
            except Exception:
                pass

        finally:
            self._done.set()


# ---------------------------------------------------------------------------
# Coordinator — main-thread event loop
# ---------------------------------------------------------------------------

class Coordinator:
    """Central event dispatcher running on the main thread.

    Replaces the old ``while running: sleep(0.1)`` loop.  Receives typed
    events from all workers and background services, makes routing
    decisions, and manages conversation state.
    """

    # Hard budget for the dynamically-generated contextual ack's
    # Chatterbox synthesis call (see _play_ack_if_still_thinking). Kept
    # well under a typical real-response synthesis time so a slow/stuck
    # ack can never hold _tts_lock anywhere near as long as a real
    # response legitimately might.
    _CONTEXTUAL_ACK_TIMEOUT_S = 2.5

    def __init__(self, *, config, event_queue: queue.Queue,
                 tts_queue: queue.Queue, listener, tts, llm,
                 skill_manager, conversation, reminder_manager=None,
                 news_manager=None, calendar_manager=None,
                 profile_manager=None, memory_manager=None,
                 context_window=None, desktop_manager=None,
                 metrics=None):
        self.config = config
        self.logger = get_logger("pipeline.coordinator", config)
        self.event_queue = event_queue
        self.tts_queue = tts_queue
        self.listener = listener
        self.tts = tts
        self.llm = llm
        self.skill_manager = skill_manager
        self.conversation = conversation
        self.reminder_manager = reminder_manager
        # Wire reminder manager and config for tool-calling dispatch
        from core.tool_executor import set_current_user_fn
        set_current_user_fn(lambda: getattr(self.conversation, 'current_user', None))
        if reminder_manager:
            from core.tool_executor import set_reminder_manager
            set_reminder_manager(reminder_manager)
        from core.tool_executor import set_config as set_tool_config, set_memory_manager, set_desktop_manager
        set_tool_config(config)
        if memory_manager:
            set_memory_manager(memory_manager)
        if desktop_manager:
            set_desktop_manager(desktop_manager)
        self.news_manager = news_manager
        self.calendar_manager = calendar_manager
        self.profile_manager = profile_manager
        self.memory_manager = memory_manager
        self.context_window = context_window
        self.desktop_manager = desktop_manager
        self.metrics = metrics

        # Web research (tool calling)
        self.web_researcher = WebResearcher(config) if config.get("llm.local.tool_calling", False) else None

        # Session stats for health reporting (must be before SelfAwareness which reads it)
        self.stats = {
            'start_time': time.time(),
            'commands_processed': 0,
            'errors': 0,
            'last_error_time': None,
            'last_error_msg': None,
        }

        # Self-awareness layer (Phase 1 of task planner)
        self.self_awareness = SelfAwareness(
            skill_manager=skill_manager,
            metrics=metrics,
            memory_manager=memory_manager,
            context_window=context_window,
            coordinator_stats=self.stats,
            config=config,
        )

        # Task planner (Phase 2-3 of task planner)
        self.task_planner = TaskPlanner(
            llm=llm,
            skill_manager=skill_manager,
            self_awareness=self.self_awareness,
            conversation=conversation,
            config=config,
            event_queue=event_queue,
            context_window=context_window,
            web_researcher=self.web_researcher,
        )

        # Centralized conversation state (Phase 2 of conversational flow refactor)
        self.conv_state = ConversationState()

        # Interaction artifact cache
        from core.interaction_cache import get_interaction_cache
        self.interaction_cache = get_interaction_cache(config=config)

        # Awareness Accumulator (CAL Component 1)
        from core.awareness_accumulator import get_awareness_accumulator
        self.accumulator = get_awareness_accumulator(
            config=config,
            calendar_manager=calendar_manager,
            reminder_manager=reminder_manager,
            news_manager=news_manager,
        )

        self.running = True
        self.state = PipelineState.IDLE
        self.wake_word = config.get("system.wake_word", "jarvis").lower()

        # Streaming LLM state
        self._streaming_active = False
        self._llm_responded = False
        self._turn_cancelled = threading.Event()
        self._stop_only_interrupt = False
        self._active_audio_pipeline = None
        self._active_response_text = ""
        self._barge_in_lock = threading.Lock()
        self._retired_audio_pipelines = []

        # Per-turn latency instrumentation (core/latency_tracker.py) —
        # one active tracker at a time, matching the existing pattern of
        # per-turn scratch state living on self (e.g. _contextual_ack_text).
        self._current_latency = None

        # Watchdog heartbeat timestamps (monotonic, read by core.watchdog)
        self._last_transcription_ts = time.monotonic()
        self._last_command_start_ts = 0.0
        self._last_command_end_ts = time.monotonic()
        self._last_idle_ts = time.monotonic()

        # Beep
        from pathlib import Path
        self.beep_path = Path(__file__).parent.parent / "assets" / "wake_word_detect.wav"

        # Share the valid short replies set from the listener (single source of truth)
        self._valid_short_replies = self.listener._valid_short_replies

        # Speaker tracking (multi-speaker rapid-switch detection)
        self._last_speaker_id: Optional[str] = None
        self._last_speaker_confidence: Optional[float] = None
        self._rapid_switch_count: int = 0
        self._last_switch_time: float = 0.0

        # People manager (social introductions + pronunciation)
        self.people_manager = None
        if config.get("people.enabled", False):
            from core.people_manager import get_people_manager
            self.people_manager = get_people_manager(config)

        # Unified awareness assembler
        self.awareness = None
        try:
            from core.awareness import AwarenessAssembler
            self.awareness = AwarenessAssembler(
                memory_manager=memory_manager,
                people_manager=self.people_manager,
                self_awareness=self.self_awareness,
                calendar_manager=self.calendar_manager,
                news_manager=news_manager,
                context_window=context_window,
                config=config,
            )
        except Exception as e:
            self.logger.warning(f"Awareness assembler init failed (non-fatal): {e}")

        # Shared command router (Phase 3 of conversational flow refactor)
        self.router = ConversationRouter(
            skill_manager=skill_manager,
            conversation=conversation,
            llm=llm,
            reminder_manager=reminder_manager,
            memory_manager=memory_manager,
            news_manager=news_manager,
            context_window=context_window,
            conv_state=self.conv_state,
            config=config,
            web_researcher=self.web_researcher,
            self_awareness=self.self_awareness,
            task_planner=self.task_planner,
            people_manager=self.people_manager,
            awareness=self.awareness,
            accumulator=self.accumulator,
        )

        # Direct audio (Gemma PRIMARY hears the turn audio itself).
        from core.direct_audio import DirectAudioService
        self.direct_audio = DirectAudioService(
            llm, config,
            context_provider=self._direct_audio_context,
            text_fallback_available=self._text_fallback_available,
            content_allowed=self._content_logging_allowed,
        )
        try:
            from core.privacy_gate import get_privacy_gate
            get_privacy_gate(config).register_flush_callback(self._privacy_flush_direct_audio)
        except Exception as exc:
            self.logger.warning("Direct audio privacy flush not registered: %s", exc)

        # Primary <-> Expert handover (None unless attach_handover() is called).
        self.handover = None
        self._pending_expert = None
        self._starting_notice_ts = 0.0

        # Wire profile manager to conversation for speaker labels
        if self.profile_manager:
            self.conversation.set_profile_manager(self.profile_manager)

        # Wire timeout cleanup so silence-expired windows get same cleanup as dismissals
        self.listener.on_window_close = self._on_conversation_timeout

    # ----- main loop -----

    def run(self):
        """Block on the event queue, dispatching events until shutdown."""
        self.logger.info("Coordinator event loop started")
        while self.running:
            self._retired_audio_pipelines = [
                pipeline for pipeline in self._retired_audio_pipelines
                if pipeline._thread is not None and pipeline._thread.is_alive()
            ]
            try:
                event = self.event_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._dispatch(event)
            except Exception as e:
                self.logger.error(
                    "Dispatch error for event type %s (%s)",
                    getattr(getattr(event, "type", None), "name", "unknown"),
                    type(e).__name__,
                )
                self.stats['errors'] += 1
                self.stats['last_error_time'] = time.time()
                self.stats['last_error_msg'] = f"dispatch: {type(e).__name__}"

        self.logger.info("Coordinator event loop exited")

    def shutdown(self):
        self.running = False

    def get_health(self) -> dict:
        """Collect JARVIS internal state for health reporting."""
        # Listener state
        listener_health = {}
        if self.listener:
            listener_health = {
                'running': getattr(self.listener, 'running', False),
                'stream_active': getattr(self.listener, 'stream', None) is not None,
                'device': getattr(self.listener, 'device', 'unknown'),
                'conversation_active': getattr(self.listener, 'conversation_window_active', False),
                'rnnoise': getattr(self.listener, 'use_rnnoise', False),
            }

        # Skills count
        skills_loaded = 0
        intent_count = 0
        if self.skill_manager:
            skills_loaded = len(getattr(self.skill_manager, 'skills', {}))
            matcher = getattr(self.skill_manager, 'matcher', None)
            if matcher and hasattr(matcher, 'get_intent_count'):
                intent_count = matcher.get_intent_count()

        # LLM state
        llm_health = {}
        if self.llm:
            llm_health = {
                'api_call_count': getattr(self.llm, 'api_call_count', 0),
                'fallback_enabled': getattr(self.llm, 'fallback_enabled', False),
                'local_model': getattr(self.llm, 'local_model_path', None) is not None,
            }

        return {
            'running': self.running,
            'state': self.state.name,
            'stats': dict(self.stats),
            'event_queue_size': self.event_queue.qsize(),
            'tts_queue_size': self.tts_queue.qsize(),
            'managers': {
                'reminders': self.reminder_manager is not None,
                'news': self.news_manager is not None,
                'calendar': self.calendar_manager is not None,
                'profiles': self.profile_manager is not None,
                'memory': self.memory_manager is not None,
                'context_window': self.context_window is not None,
                'desktop': self.desktop_manager is not None,
            },
            'listener': listener_health,
            'tts_engine': getattr(self.tts, 'engine', 'unknown'),
            'llm': llm_health,
            'skills_loaded': skills_loaded,
            'semantic_intents': intent_count,
        }

    # ----- dispatch -----

    def _dispatch(self, event: Event):
        handlers = {
            EventType.TRANSCRIPTION_READY: self._handle_transcription,
            EventType.COMMAND_DETECTED: self._handle_command,
            EventType.PAUSE_LISTENING: lambda e: self.listener.pause_listening(),
            EventType.RESUME_LISTENING: self._handle_resume,
            EventType.OPEN_CONVERSATION_WINDOW: lambda e: self.listener.open_conversation_window(e.data),
            EventType.CLOSE_CONVERSATION_WINDOW: self._handle_close_conversation,
            EventType.SPEECH_STARTED: self._handle_speech_started,
            EventType.SPEECH_FINISHED: self._handle_speech_finished,
            EventType.LLM_COMPLETE: self._handle_llm_complete,
            EventType.SHUTDOWN: lambda e: self.shutdown(),
            EventType.ERROR: self._handle_error,
        }
        handler = handlers.get(event.type)
        if handler:
            handler(event)
        else:
            self.logger.debug(f"Unhandled event: {event.type.name}")

    # ----- transcription handling (extracted from _transcribe_and_check) -----

    def _handle_transcription(self, event: Event):
        """Process raw transcription text: validate, check wake word or
        conversation window, and emit COMMAND_DETECTED if appropriate."""
        self._last_transcription_ts = time.monotonic()
        audio_turn_id = None
        # Extract text and speaker context from enriched or plain event data
        if isinstance(event.data, dict):
            raw_text = event.data["text"]
            speaker_id = event.data.get("speaker_id")
            speaker_confidence = event.data.get("speaker_confidence", 0.0)
            generation = event.data.get("capture_generation")
            audio_turn_id = event.data.get("audio_turn_id")
            if (generation is not None and not event.data.get("barge_in")
                    and generation != getattr(self.listener, "_capture_generation", generation)):
                self.logger.info("Discarded stale transcription from an earlier audio generation")
                self.reject_audio_turn(audio_turn_id, "stale")
                return
            self._apply_speaker_context(speaker_id, speaker_confidence)
        else:
            raw_text = event.data

        text = raw_text.lower()

        # Filter noise annotations
        if (text.startswith('(') and text.endswith(')')) or \
           (text.startswith('[') and text.endswith(']')):
            self.logger.info("Ignoring Whisper noise annotation (%d chars)", len(text))
            print("⚠️  Ignoring background noise")
            self.reject_audio_turn(audio_turn_id, "noise")
            return

        # Filter garbage (repetitive chars from TTS bleed, etc.)
        if is_garbage_transcription(text):
            self.logger.info("Ignoring garbage transcription (%d chars)", len(text))
            self.reject_audio_turn(audio_turn_id, "garbage")
            return

        # Apply brand-name corrections (quinn→qwen, etc.) before any routing
        text = self._apply_transcription_corrections(text)

        self.logger.info("Transcription received (%d chars)", len(text))

        # Direct-audio turn: the model already got the audio. The transcript is
        # metadata (asr_hint) plus the wake gate for speculative turns.
        if audio_turn_id is not None:
            if self.direct_audio.get(audio_turn_id) is None:
                # Turn already answered, diverted, rejected or cancelled (privacy/stop):
                # the transcript must NOT re-enter the legacy text path.
                self.logger.info("Transcript of a finished direct-audio turn ignored")
                return
            if self._resolve_direct_turn_from_transcript(audio_turn_id, text):
                return

        # Conversation window — accept without wake word
        if self.listener.conversation_window_active:
            if self._is_conversation_noise(text):
                self.logger.info("Filtered speech during conversation (%d chars)", len(text))
                return
            if find_wake_word(text, self.wake_word):
                text = strip_wake_word(text, self.wake_word) or "jarvis_only"
            text = self._apply_command_corrections(text)
            self.listener._cancel_conversation_timer()
            self.logger.info("Accepting conversation response (%d chars)", len(text))
            self.event_queue.put(Event(
                EventType.COMMAND_DETECTED,
                data=text,
                source="coordinator",
            ))
            return

        wake_match = find_wake_word(text, self.wake_word)
        if wake_match:
            _, _, matched_word, similarity = wake_match
            self.logger.info("Wake word detected (similarity: %.2f)", similarity)
            # Check if this is ambient conversation rather than a command
            if self._is_ambient_wake_word(text, matched_word):
                print("🔇 Ambient mention (ignored)")
                return

            corrected_text = strip_wake_word(text, self.wake_word)
            self.logger.info("Normalized wake-word transcript (%d chars)", len(text))
            self.event_queue.put(Event(
                EventType.COMMAND_DETECTED,
                data=corrected_text,
                source="coordinator",
            ))
        else:
            self.logger.info("No wake word detected (%d chars)", len(text))
            print("❌ No wake word (ignored)")

    # ----- command processing (extracted from on_command_detected) -----

    def _handle_command(self, event: Event):
        """Route a detected command through the priority chain."""
        self._current_direct = None
        try:
            self._handle_command_impl(event)
        finally:
            current, self._current_direct = self._current_direct, None
            if current is not None:
                self.direct_audio.finish(current)   # drop tracking/timer of the popped turn

    def _handle_command_impl(self, event: Event):
        self._last_command_start_ts = time.monotonic()
        self._turn_cancelled.clear()
        self._stop_only_interrupt = False
        self._active_response_text = ""
        self._pending_expert = None      # never leak a delegation into another turn
        self._current_latency = LatencyTracker()
        direct = None
        if isinstance(event.data, dict) and event.data.get("direct_audio_turn") is not None:
            direct = self.direct_audio.pop(event.data["direct_audio_turn"], active=True)
            self._current_direct = direct
            if (direct is None
                    or (direct.turn.is_rejected and not direct.superseded)
                    or (direct.generation is not None
                        and direct.generation != getattr(self.listener, "_capture_generation",
                                                         direct.generation))):
                if direct is not None:
                    direct.turn.cancel()
                self.logger.info("Direct audio turn no longer valid; ignored")
                return
            full_text = direct.placeholder
            in_conversation = direct.in_conversation
        else:
            full_text = event.data
            in_conversation = self.listener.conversation_window_active
        self.state = PipelineState.PROCESSING_COMMAND
        self.stats['commands_processed'] += 1

        if direct is not None:
            # STT verdict for held (conversation window) turns: release / text path / reject.
            outcome, verdict_command = self._await_direct_verdict(direct)
            if outcome == "abort":
                self.logger.info("Direct audio turn ended without answer (%s)",
                                 direct.verdict_reason or "cancelled")
                if self._turn_cancelled.is_set():
                    self._finish_cancelled_turn()
                else:
                    self.listener.resume_listening()
                    self.state = PipelineState.IDLE
                    self._last_command_end_ts = self._last_idle_ts = time.monotonic()
                return
            if outcome == "text":
                # Tool/skill/canned turn or bare wake: normal text pipeline
                # (router.route / _handle_minimal_greeting), no Gemma request.
                self.logger.info("Direct audio turn -> text path (%s)", direct.verdict_reason)
                full_text = verdict_command
                direct = None
            else:
                self._finalize_direct_context(direct)

        # Parse input
        if direct is not None:
            command = direct.placeholder
            if not in_conversation and self.memory_manager:
                self.memory_manager.reset_surfacing_window()
        elif in_conversation:
            self.logger.info("Conversation continues (%d chars)", len(full_text))
            if find_wake_word(full_text, self.wake_word):
                command = self._extract_command(full_text)
            else:
                command = full_text
        else:
            self.logger.info("Command detected (%d chars)", len(full_text))
            command = self._extract_command(full_text)
            # Fresh wake-word activation — reset memory surfacing window
            # (covers conversation timeout path where no explicit close event fires)
            if self.memory_manager:
                self.memory_manager.reset_surfacing_window()

        # Pause listening while we process
        self.listener.pause_listening()

        # Beep to acknowledge: wake-word activation OR conversation-window follow-up
        if direct is not None:
            self._play_beep()
        elif not in_conversation and find_wake_word(full_text, self.wake_word):
            self._play_beep()
        elif in_conversation:
            self._play_beep()

        if not command:
            self.logger.warning("No command extracted")
            self.listener.resume_listening()
            self.state = PipelineState.IDLE
            self._last_command_end_ts = self._last_idle_ts = time.monotonic()
            return

        self.logger.info("Processing command (%d chars)", len(command.strip()))

        # --- Minimal greeting (voice-specific: adds "jarvis" to history) ---
        if command.strip() == "jarvis_only" or len(command.strip()) <= 2:
            self._handle_minimal_greeting(command, in_conversation)
            return

        # --- Process real command ---
        self.logger.debug("Passing command to router (%d chars)", len(command))
        if direct is not None:
            # The turn actually processed by the model: audio turn id +
            # placeholder. The ASR transcript is only an asr_hint annotation.
            from core.direct_audio import store_user_turn
            store_user_turn(self.conversation, direct,
                            speaker_confidence=self._last_speaker_confidence)
        else:
            self.conversation.add_message(
                "user", command,
                speaker_confidence=self._last_speaker_confidence,
                client_id="voice",
            )
        self.tts._spoke = False

        # --- Rapid speaker-switch retort (humorous "one at a time" interjection) ---
        if self._rapid_switch_count >= 3:
            from core import persona
            from core.honorific import get_honorific
            retort = persona.speaker_switch_retort(get_honorific())
            self.logger.info(f"Rapid switch retort (count={self._rapid_switch_count})")
            self._speak_and_wait(retort)
            self._rapid_switch_count = 0

        # --- Pre-route ack decision (must happen BEFORE routing, which blocks) ---
        ack_style, suppress_ack = self._classify_ack(
            command,
            in_conversation=in_conversation,
            jarvis_asked_question=self.conv_state.jarvis_asked_question,
        )
        if direct is not None:
            suppress_ack = True   # no text to build an ack from; the LLM stream acks itself

        # --- Fire contextual ack generation in background (4B, ~600ms) ---
        # Runs in parallel with routing. If ready by the time the 1.5s timer
        # fires, the user hears a contextual ack. If not, falls back to
        # the generic cached ack.
        self._contextual_ack_text = None
        if not suppress_ack:
            from core.honorific import get_honorific
            _ack_cmd = command
            _ack_hon = get_honorific()
            def _gen_ack():
                from core.persona import generate_contextual_ack
                self._contextual_ack_text = generate_contextual_ack(
                    _ack_cmd, self.llm, _ack_hon,
                )
            _ack_thread = threading.Thread(target=_gen_ack, daemon=True)
            _ack_thread.start()

        # --- Route through shared priority chain ---
        # For skill-handled commands, play an ack if warranted (the skill
        # handler may take tens of seconds, e.g. document generation).
        # Timer at 1.5s: routing + fast skills complete in <1s, so the ack
        # only fires for genuinely slow operations (doc gen, web research).
        self._llm_responded = False
        ack_timer = None
        if not suppress_ack:
            ack_timer = threading.Timer(
                1.5, self._play_ack_if_still_thinking, args=(ack_style,)
            )
            ack_timer.daemon = True
            ack_timer.start()

        if direct is not None:
            result = self._direct_route_result(direct)
        else:
            result = self.router.route(command, in_conversation=in_conversation)
        self._current_latency.mark("router_done")

        # Cancel ack timer if skill returned before it fired
        if ack_timer:
            ack_timer.cancel()
            self._llm_responded = True

        # Skip: bare acknowledgment noise
        if result.skip:
            self.logger.info("Router: skip (bare ack noise)")
            self.listener.resume_listening()
            self.state = PipelineState.IDLE
            self._last_command_end_ts = self._last_idle_ts = time.monotonic()
            return

        if result.handled:
            response = result.text

            # Task plan: speak announcement, then execute the plan
            if result.intent == "task_plan" and self.task_planner.active_plan:
                if response:
                    self._speak_and_wait(response)
                response = self._execute_task_plan()
            elif response and not self.tts._spoke:
                # Speak response (unless handler already spoke via TTS proxy,
                # e.g. deliver_rundown or a skill that calls tts.speak directly).
                # CAL-L0 responses are auto-cached in tts.speak() — no special
                # handling needed here.
                self._speak_and_wait(response)

            if self._turn_cancelled.is_set():
                self._finish_cancelled_turn()
                return

            # Conversation window side effects
            if result.close_window:
                self._handle_close_conversation(None)
            elif result.open_window is not None:
                self.listener.open_conversation_window(result.open_window)
        else:
            # Explicit expert wish / escalation: ALWAYS through the handover, never a direct
            # role='expert' stream while the primary may be resident on the GPU.
            if (getattr(result, "model_role", "primary") == "expert"
                    or getattr(result, "expert_requested", False)):
                if self._expert_available():
                    self._run_expert_turn(self._expert_request_from_route(command, result),
                                          in_conversation=in_conversation, route=result)
                    if self._turn_cancelled.is_set():
                        self._finish_cancelled_turn()
                        return
                    self.listener.resume_listening()
                    self.state = PipelineState.IDLE
                    self._last_command_end_ts = self._last_idle_ts = time.monotonic()
                    return
                self.logger.warning("Expert requested but handover/expert not available; primary answers")
                self._speak_and_wait("Der Experte ist derzeit nicht verfügbar. Ich antworte selbst.")
            # LLM fallback (streaming)
            print("🤖 Thinking...")
            if direct is None:
                unavailable = self._await_primary()
                if unavailable:
                    self._speak_and_wait(unavailable)
                    self.conversation.add_message("assistant", unavailable, client_id="voice")
                    self.listener.resume_listening()
                    self.state = PipelineState.IDLE
                    self._last_command_end_ts = self._last_idle_ts = time.monotonic()
                    return
            response = self._stream_llm_response(
                result.llm_command, result.llm_history,
                memory_context=result.memory_context,
                conversation_messages=result.context_messages,
                raw_command=command,
                in_conversation=in_conversation,
                use_tools=result.use_tools,
                tool_temperature=result.tool_temperature,
                tool_presence_penalty=result.tool_presence_penalty,
                synthesis_temperature=result.synthesis_temperature,
                synthesis_category=result.synthesis_category,
                force_web_search=result.force_web_search,
                force_tool_call=result.force_tool_call,
                token_source_override=(direct.turn.stream(decision_timeout=15.0)
                                       if direct is not None else None),
                role=None,   # primary only; the expert is reached exclusively via the handover
            )
            if self._turn_cancelled.is_set():
                self._finish_cancelled_turn()
                return
            if not response:
                if direct is not None and direct.failure:
                    response = "Das Sprachmodell ist noch nicht bereit. Bitte gleich noch einmal."
                else:
                    response = "Entschuldigung, ich kann das gerade nicht verarbeiten."

        # Post-process: strip metric conversions Qwen sneaks in, then filler for history
        response = self.llm.strip_metric(response, command) if response else response
        stored_response = self.llm.strip_filler(response) if response else response
        self.conversation.add_message("assistant", stored_response, client_id="voice")
        print(f"💬 Jarvis: {response}")
        if not self.tts._spoke:
            self._speak_and_wait(response)

        if self._current_latency:
            self._current_latency.mark("response_done")
            self._current_latency.emit(self.logger, self.config)
            self._current_latency = None

        # Update centralized conversation state
        self.conv_state.update(
            command=command,
            response_text=response or "",
            response_type="llm" if not result.handled else "skill",
        )

        # Record metrics for ALL interactions (skills, CAL-L0, LLM, etc.)
        used_llm = not result.handled or result.used_llm
        self._record_metrics(result, used_llm)

        # The primary called delegate_to_expert during this turn: run the handover now that
        # the primary's own answer is finished (the expert answer goes straight to TTS).
        pending_expert, self._pending_expert = getattr(self, "_pending_expert", None), None
        if pending_expert is not None and not self._turn_cancelled.is_set():
            self._run_expert_turn(pending_expert, in_conversation=in_conversation)

        # Follow-up window — handled results with explicit window instructions
        # skip the default window management
        if result.handled and (result.close_window or result.open_window is not None):
            pass  # Already handled above
        elif self.conversation.request_follow_up:
            duration = self.conversation.request_follow_up
            self.conversation.request_follow_up = None
            self.listener.open_conversation_window(duration)
        else:
            self._manage_conversation_window(response, in_conversation)

        # CAL: Post-task awareness nudge — surface one critical item after
        # substantive tasks (tool calls, LLM responses). Skip for quick
        # conversational exchanges (CAL-L0 greetings, bare acks).
        _is_substantive = used_llm or (result.handled and result.source not in ("cal_l0", "dismissal"))
        if (_is_substantive and self.accumulator
                and getattr(self.conversation, 'current_user', None) != '__guest__'):
            try:
                _user_id = getattr(self.conversation, 'current_user', None) or 'christopher'
                _nudge_items = self.accumulator.get_top(
                    n=1, threshold=0.6, user_id=_user_id,
                )
                if _nudge_items:
                    from core.awareness_accumulator import compose_briefing
                    from core.honorific import get_honorific
                    _display_name = _user_id.capitalize() if _user_id else ""
                    _nudge_text = compose_briefing(
                        _nudge_items, self.llm,
                        honorific=get_honorific(),
                        user_name=_display_name,
                        moment_type="task_end",
                    )
                    if _nudge_text:
                        self.logger.info(
                            "CAL nudge prepared (%d chars)", len(_nudge_text),
                        )
                        self._speak_and_wait(_nudge_text)
                        self.accumulator.mark_surfaced(_nudge_items, _user_id)
            except Exception as e:
                self.logger.warning("CAL post-task nudge failed: %s", e)

        # Stats and resume
        stats = self.conversation.get_conversation_stats()
        print(f"\n📊 Session: {stats['session_user_messages']} user, "
              f"{stats['session_assistant_messages']} assistant messages\n")
        self.listener.resume_listening()
        self.state = PipelineState.IDLE
        self._last_command_end_ts = self._last_idle_ts = time.monotonic()

    # ----- minimal greeting -----

    def _handle_minimal_greeting(self, command: str, in_conversation: bool):
        self.logger.info("Minimal greeting - just wake word")
        if (getattr(self.conversation, 'current_user', None) != "__guest__"
                and self.reminder_manager and self.reminder_manager.has_rundown_mention()):
            self.reminder_manager.clear_rundown_mention()
            response = persona.rundown_mention()
        elif getattr(self.conversation, 'current_user', None) == "__guest__":
            response = persona.guest_greeting()
        else:
            response = persona.pick("greeting")

        self.conversation.add_message("user", "jarvis", client_id="voice")
        if response:
            self.conversation.add_message("assistant", response, client_id="voice")
            print(f"💬 Jarvis: {response}")
            self._speak_and_wait(response)
            if self._turn_cancelled.is_set():
                self._finish_cancelled_turn()
                return

        self.listener.open_conversation_window(self.listener._extended_duration)
        self.listener.resume_listening()
        self.state = PipelineState.IDLE
        self._last_command_end_ts = self._last_idle_ts = time.monotonic()

    # ----- task plan execution -----

    def _execute_task_plan(self) -> str:
        """Execute the active task plan with TTS progress callbacks.

        Phase 3: Resumes listener during plan execution so voice interrupts
        can be captured. Handles cancellation and partial completion outcomes.
        """
        from core.task_planner import PlanStatus

        plan = self.task_planner.active_plan
        if not plan:
            return "Entschuldigung, der Plan ging verloren, bevor ich ihn ausführen konnte."

        def progress_callback(description: str):
            """Speak progress between steps."""
            msg = persona.task_progress(description)
            print(f"📋 {msg}")
            self._speak_and_wait(msg)

        # Resume listening so voice interrupts ("stop", "cancel") are captured
        self.listener.resume_listening()

        result = self.task_planner.execute_plan(
            plan, progress_callback=progress_callback,
        )

        # Pause listening before speaking outcome
        self.listener.pause_listening()

        # Speak outcome based on plan status
        completed_count = sum(
            1 for s in plan.steps
            if s.status.value == "completed"
        )
        total = len(plan.steps)

        if plan.status == PlanStatus.CANCELLED:
            if completed_count > 0:
                # Partial completion — speak partial message + result
                msg = persona.task_partial(completed_count, total)
                print(f"📋 {msg}")
                self._speak_and_wait(msg)
            else:
                msg = persona.task_cancelled()
                print(f"📋 {msg}")
                self._speak_and_wait(msg)
        elif result:
            completion = persona.task_complete()
            print(f"📋 {completion}")
            self._speak_and_wait(completion)

        return result or ""

    # ----- streaming LLM -----

    def _stream_llm_response(self, command: str, history: str,
                              memory_context: str = None,
                              conversation_messages: list = None,
                              raw_command: str = None,
                              in_conversation: bool = False,
                              use_tools: list = None,
                              tool_temperature: float = None,
                              tool_presence_penalty: float = None,
                              synthesis_temperature: float = None,
                              synthesis_category: str = None,
                              force_web_search: bool = False,
                              force_tool_call: str = None,
                              token_source_override=None,
                              role: str = None,
                              audio_data: str = None) -> str:
        """Stream LLM response with first-chunk quality gating and tool calling.

        token_source_override: pre-started (possibly speculative) item stream,
            e.g. SpeculativeTurn.stream(); replaces the llm.stream* call.
        role: 'primary' (default) or 'expert' (Qwen, explicit delegation only).

        Streams tokens from Qwen, accumulates into sentence chunks,
        and speaks each chunk via a persistent aplay process for
        gapless multi-sentence playback.

        When tool calling is enabled, the LLM may request a tool call
        instead of generating text. The pipeline will execute the tool,
        feed results back, and stream the synthesized answer.

        Args:
            command: The (possibly augmented) text to send to the LLM.
            raw_command: The original user query before context augmentation.
                         Used for tool_choice regex and research exchange storage.
                         Falls back to command if not provided.
            use_tools: When set by the router's P4-LLM path, list of tool
                       schema dicts to pass to stream_with_tools().
            tool_temperature: Override temperature for tool selection phase.
            tool_presence_penalty: Presence penalty for tool-calling requests.
            force_web_search: Force a web_search call without LLM tool selection.
        """
        if raw_command is None:
            raw_command = command
        if role is not None and str(role).lower() == "expert":
            # Direct role='expert' streams are only legal inside the handover's call_expert
            # (primary stopped, expert running). Here the primary may be resident.
            self.logger.warning("role='expert' stream refused outside the handover; using primary")
            role = None
        guest_mode = getattr(self.conversation, 'current_user', None) == '__guest__'
        if guest_mode:
            memory_context = None
        chunker = SpeechChunker()
        voice_boundary = VoiceTagBoundaryBuffer()
        full_response = ""
        chunks_spoken = 0
        first_chunk_checked = False

        # Ack style for LLM streaming path. Unlike the pre-route ack,
        # we NEVER suppress here — if we reached _stream_llm_response,
        # routing didn't handle it, so the user is about to wait for LLM
        # generation. They should always hear an ack. (B11 fix)
        ack_style, _ = self._classify_ack(
            raw_command,
            in_conversation=in_conversation,
            jarvis_asked_question=self.conv_state.jarvis_asked_question,
        )
        self._llm_responded = False
        ack_timer = threading.Timer(
            0.3, self._play_ack_if_still_thinking, args=(ack_style,)
        )
        ack_timer.daemon = True
        ack_timer.start()

        # Gapless audio pipeline (Kokoro, Chatterbox — overlaps generation
        # with playback on a persistent aplay pipe). Piper has no streaming
        # API and falls back to per-sentence blocking speak_and_wait.
        use_pipeline = self.tts.engine in ("kokoro", "chatterbox")
        audio_pipeline = None

        # Choose tool-aware or plain streaming
        _enable_tools = self.llm.tool_calling and (self.web_researcher or use_tools)

        try:
            pending_chunk = None
            tool_call_request = None

            # --- Phase A: stream from LLM (may yield ToolCallRequest) ---
            token_source = token_source_override if token_source_override is not None else (
                self.llm.stream_with_tools(
                    user_message=command,
                    conversation_history=history,
                    memory_context=memory_context,
                    conversation_messages=conversation_messages,
                    raw_command=raw_command,
                    tools=use_tools,
                    tool_temperature=tool_temperature,
                    tool_presence_penalty=tool_presence_penalty,
                    force_web_search=force_web_search,
                    force_tool_call=force_tool_call,
                    guest_mode=guest_mode,
                    role=role, audio_data=audio_data,
                ) if _enable_tools else
                self.llm.stream(
                    user_message=command,
                    conversation_history=history,
                    memory_context=memory_context,
                    conversation_messages=conversation_messages,
                    guest_mode=guest_mode,
                    role=role, audio_data=audio_data,
                )
            )

            if self._current_latency:
                self._current_latency.mark("llm_start")

            for item in token_source:
                if self._turn_cancelled.is_set():
                    break
                if self._current_latency:
                    self._current_latency.mark("llm_first_token")

                # Tool call sentinel — break to Phase B
                if isinstance(item, ToolCallRequest):
                    tool_call_request = item
                    if not self._llm_responded:
                        self._llm_responded = True
                        if ack_timer:
                            ack_timer.cancel()
                    break

                # Regular token
                token = item
                if not self._llm_responded:
                    self._llm_responded = True
                    if ack_timer:
                        ack_timer.cancel()

                full_response += token
                self._active_response_text = full_response
                self.listener.active_tts_text = full_response
                safe_token = voice_boundary.feed(token)
                log_diagnostics(self.logger, voice_boundary.diagnostics)
                voice_boundary.diagnostics.clear()
                chunk = chunker.feed(safe_token) if safe_token else None

                if chunk:
                    if self._current_latency:
                        self._current_latency.mark("first_speakable_chunk")
                    chunks_spoken, first_chunk_checked, pending_chunk, audio_pipeline = \
                        self._process_speech_chunk(
                            chunk, command, history, memory_context,
                            conversation_messages, chunks_spoken,
                            first_chunk_checked, pending_chunk,
                            audio_pipeline, use_pipeline,
                        )
                    self._active_audio_pipeline = audio_pipeline
                    if chunks_spoken == -1:  # quality gate failed
                        return pending_chunk  # contains fallback response

            # --- Phase B: handle tool call if requested ---
            if self._turn_cancelled.is_set():
                return ""
            # Multi-tool loop: execute tool, synthesize, repeat if LLM
            # requests another tool (e.g. "time and weather" → get_time then get_weather).
            # Cap at 3 to prevent runaway loops.
            _MAX_TOOL_CHAIN = 5
            tool_chain_count = 0
            _tool_call_counts = {}  # Per-turn dedup: {tool_name: count}
            self._last_tools_called = []  # For metrics recording
            # Per-tool dedup limits: web_search gets 5 (multi-source queries
            # like trip cost need gas + tolls + food + hotels + activities),
            # other tools stay at 2.
            _TOOL_DEDUP_LIMITS = {'web_search': 3}

            while tool_call_request and tool_chain_count < _MAX_TOOL_CHAIN:
                tool_chain_count += 1

                _tc_name = tool_call_request.name
                advertised_tools = ({tool["function"]["name"] for tool in use_tools}
                                    if use_tools is not None else {"web_search"})
                if (_tc_name not in advertised_tools
                        or (guest_mode and _tc_name not in {"get_weather", "web_search"})):
                    self.logger.warning("Rejected unauthorized voice tool call: %s", _tc_name)
                    if ack_timer:
                        ack_timer.cancel()
                    self._llm_responded = True
                    if audio_pipeline:
                        audio_pipeline.cancel()
                    self._active_audio_pipeline = None
                    self.tts._spoke = False
                    return ("Für diese persönliche Aktion ist eine erkannte Stimme erforderlich."
                            if guest_mode else "Dieses Werkzeug ist hier nicht verfügbar.")

                # Deduplication: skip if tool exceeds its per-turn limit
                _tool_call_counts[_tc_name] = _tool_call_counts.get(_tc_name, 0) + 1
                _dedup_limit = _TOOL_DEDUP_LIMITS.get(_tc_name, 2)
                if _tool_call_counts[_tc_name] > _dedup_limit:
                    self.logger.warning(
                        "⚠️ Dedup: %s called %d times this turn (limit %d) — "
                        "skipping, synthesizing from prior results",
                        _tc_name, _tool_call_counts[_tc_name], _dedup_limit,
                    )
                    break

                self.logger.info(
                    f"🔧 Tool call: {tool_call_request.name}({tool_call_request.arguments})"
                )
                self._last_tools_called.append(tool_call_request.name)

                # Execute the tool
                tool_image_data = None  # Set by multimodal tools (e.g. take_screenshot)
                if tool_call_request.name == "web_search":
                    query = tool_call_request.arguments.get("query", command)
                    print(f"🔍 Searching: {query}")
                    # Trim fetch volume on 2nd+ search — snippets alone
                    # provide sufficient factual density for sub-queries.
                    _is_followup = _tool_call_counts.get("web_search", 0) > 1
                    _max_res = 3 if _is_followup else 5
                    _max_chars = 2000 if _is_followup else 4000
                    results = self.web_researcher.search(query, max_results=_max_res)
                    self.conv_state.research_results = results
                    _backend = getattr(self.web_researcher, 'last_backend', None) or "unknown"

                    page_sections = self.web_researcher.fetch_pages_parallel(
                        results, max_results=_max_res, max_chars=_max_chars,
                    )
                    page_content = ""
                    if page_sections:
                        page_content = "\n\nFull article content:\n\n" + \
                            "\n\n---\n\n".join(page_sections)

                    tool_result = format_search_results(results) + page_content
                    self.logger.info("Web search (%s): %d results", _backend, len(results))
                    print(f"📋 Found {len(results)} results ({_backend})")

                    # Emit tool_completed for voice pipeline web_search
                    try:
                        from core.event_logger import get_event_logger
                        _el = get_event_logger()
                        if _el:
                            _el.emit(event="tool_completed", category="tool_execution",
                                     stage="web_search", status="success",
                                     message=f"web_search: {query[:80]}",
                                     metadata={"tool": "web_search", "query": query,
                                               "results_count": len(results) if results else 0,
                                               "backend": _backend})
                    except Exception:
                        pass

                    # Artifact cache (dual-write alongside conv_state)
                    if self.interaction_cache:
                        from core.interaction_cache import Artifact
                        import uuid as _uuid
                        _wid = self.interaction_cache.ensure_window_id(self.conv_state)
                        _uid = getattr(self.conversation, 'current_user', None) or 'christopher'
                        self.interaction_cache.store(Artifact(
                            artifact_id=_uuid.uuid4().hex[:16],
                            turn_id=self.conv_state.turn_count,
                            item_index=0,
                            artifact_type="search_result_set",
                            content=tool_result,
                            summary=f"Web search: {query} ({len(results)} results)",
                            source="web_search",
                            provenance={"query": query, "result_urls": [
                                {"title": r.get("title", ""), "url": r.get("url", "")}
                                for r in results
                            ]},
                            metadata={"result_count": len(results)},
                            parent_id=None,
                            user_id=_uid,
                            window_id=_wid,
                            tier="hot",
                            created_at=time.time(),
                        ))
                else:
                    from core.tool_executor import execute_tool
                    from core.tool_registry import parse_tool_result, save_tool_image
                    print(f"🔧 Running: {tool_call_request.name}")
                    raw_result = execute_tool(
                        tool_call_request.name, tool_call_request.arguments
                    )
                    tool_result, tool_image_data = parse_tool_result(raw_result)
                    self.logger.info("Tool completed (result length=%d)", len(tool_result or ""))
                    self.logger.debug("Tool result metrics: full_len=%d image=%s%s",
                                      len(tool_result) if tool_result else 0,
                                      "yes" if tool_image_data else "no",
                                      f" ({len(tool_image_data)//1024}KB b64)" if tool_image_data else "")

                    # Save tool-generated images to disk
                    image_path = None
                    if tool_image_data:
                        image_path = save_tool_image(tool_image_data, tool_call_request.name)

                    # Artifact cache — store non-web-search tool results
                    if self.interaction_cache:
                        from core.interaction_cache import store_tool_artifact
                        store_tool_artifact(
                            tool_call_request.name, tool_call_request.arguments,
                            tool_result, self.interaction_cache, self.conv_state,
                            user_id=getattr(self.conversation, 'current_user', None) or 'christopher',
                            image_path=image_path,
                        )

                    # "Show me" display hook for developer_tools
                    if tool_call_request.name == "developer_tools":
                        action = tool_call_request.arguments.get("action", "")
                        show_me = _detect_show_me(command)

                        # system_health ALWAYS displays (the visual report is
                        # the whole point of the feature — no "show me" needed)
                        if action == "system_health":
                            show_me = show_me or "auto"

                        if (show_me and tool_result
                                and not tool_result.startswith(("BLOCKED", "CONFIRMATION REQUIRED", "Error"))):
                            ct, title = _DEVTOOLS_DISPLAY_MAP.get(action, ("general", "Output"))
                            # For system_health, generate the full visual report
                            # instead of the compact tool output
                            display_content = tool_result
                            if action == "system_health":
                                try:
                                    from core.health_check import get_full_health, format_visual_report
                                    health = get_full_health(self.config)
                                    display_content = format_visual_report(health)
                                except Exception:
                                    pass  # fall back to plain tool_result
                            backend = show_me if show_me in ("terminal", "vscode") else None
                            try:
                                _get_display_router(self.config).show(
                                    display_content, content_type=ct, title=title,
                                    force_backend=backend,
                                )
                            except Exception as e:
                                self.logger.warning(f"Display hook error: {e}")

                # Store compact tool result for follow-up context.
                # This powers anaphoric references ("list them", "which ones?")
                # by giving the next turn access to the actual tool data.
                _tool_summary = tool_result[:800] if tool_result else ""
                self.conv_state.last_tool_result_text = (
                    f"[{tool_call_request.name}] {_tool_summary}"
                )
                if self._turn_cancelled.is_set():
                    return ""

                # Stream synthesis — may yield text tokens or another ToolCallRequest
                _synth_img = tool_image_data if tool_call_request.name != "web_search" else None
                self.logger.debug("Synthesis loop: tool=%s result_len=%d image=%s tools=%s",
                                  tool_call_request.name,
                                  len(tool_result) if tool_result else 0,
                                  f"yes ({len(_synth_img)//1024}KB)" if _synth_img else "no",
                                  [t["function"]["name"] for t in use_tools] if use_tools else "none")
                next_tool_call = None
                _synth_token_count = 0

                # Result compression: on 2nd+ tool call, compress ALL prior
                # tool-role messages in _tool_call_messages before the next
                # synthesis call builds its payload. This must happen BEFORE
                # continue_after_tool_call, which appends the new tool result
                # and sends the full message list to the LLM.
                if tool_chain_count > 1 and hasattr(self.llm, '_tool_call_messages'):
                    _tcm = self.llm._tool_call_messages
                    for _i, _msg in enumerate(_tcm):
                        if _msg.get('role') == 'tool':
                            _raw_len = len(_msg.get('content', ''))
                            if _raw_len > 600:
                                _msg['content'] = (
                                    f"[Summary of prior search results]: "
                                    f"{_msg['content'][:500]}"
                                )
                                self.logger.debug(
                                    "Compressed prior tool result [%d]: %d→%d chars",
                                    _i, _raw_len, len(_msg['content']),
                                )

                # Scale max_tokens with chain depth — multi-source answers
                # (e.g. trip cost: gas + tolls + food) need more output budget.
                _synth_max_tokens = 400 + (tool_chain_count * 100)
                # Buffer intermediate text — discard if followed by a chained tool call
                _intermediate_buffer = ""
                for item in self.llm.continue_after_tool_call(
                    tool_call_request, tool_result,
                    max_tokens=_synth_max_tokens,
                    tools=use_tools,
                    image_data=_synth_img,
                    synthesis_temperature=synthesis_temperature,
                    synthesis_category=synthesis_category,
                    guest_mode=guest_mode,
                    role=role,
                ):
                    if self._turn_cancelled.is_set():
                        break
                    if isinstance(item, ToolCallRequest):
                        self.logger.debug("Chained tool call from synthesis: %s "
                                          "(discarding %d chars intermediate text)",
                                          item.name, len(_intermediate_buffer))
                        next_tool_call = item
                        break

                    _intermediate_buffer += item
                    _synth_token_count += 1

                if self._turn_cancelled.is_set():
                    return ""

                if next_tool_call is None and _intermediate_buffer:
                    # Final synthesis — commit buffered text to response
                    if not self._llm_responded:
                        self._llm_responded = True
                    full_response += _intermediate_buffer
                    # Re-feed buffered text through chunker for TTS
                    for char in _intermediate_buffer:
                        safe_char = voice_boundary.feed(char)
                        log_diagnostics(self.logger, voice_boundary.diagnostics)
                        voice_boundary.diagnostics.clear()
                        chunk = chunker.feed(safe_char) if safe_char else None
                        if chunk:
                            chunks_spoken, first_chunk_checked, pending_chunk, audio_pipeline = \
                                self._process_speech_chunk(
                                    chunk, command, history, memory_context,
                                    conversation_messages, chunks_spoken,
                                    first_chunk_checked, pending_chunk,
                                    audio_pipeline, use_pipeline,
                                )
                            if chunks_spoken == -1:
                                return pending_chunk

                self.logger.debug("Synthesis complete: %d tokens, response_len=%d",
                                  _synth_token_count, len(full_response))

                tool_call_request = next_tool_call

            # Graceful partial results: if synthesis produced nothing but we
            # executed tools successfully, collect compressed summaries from
            # _tool_call_messages and ask the LLM to synthesize them directly.
            if not full_response.strip() and tool_chain_count > 0:
                self.logger.warning(
                    "Synthesis empty after %d tool calls — attempting partial fallback",
                    tool_chain_count,
                )
                _tcm = getattr(self.llm, '_tool_call_messages', [])
                _summaries = [
                    m['content'] for m in _tcm
                    if m.get('role') == 'tool' and m.get('content')
                ]
                if _summaries:
                    _fallback_prompt = (
                        f"The user asked: {command}\n\n"
                        "Here is the information gathered:\n\n"
                        + "\n\n".join(_summaries)
                        + "\n\nSynthesize a concise, complete answer."
                    )
                    try:
                        full_response = self.llm.chat(
                            _fallback_prompt, [], max_tokens=600,
                            guest_mode=guest_mode,
                        ) or ""
                        if full_response.strip():
                            self.logger.info("Partial fallback succeeded: %d chars", len(full_response))
                    except Exception as e:
                        self.logger.error("Partial fallback also failed: %s", e)

            # Combine buffered last chunk + flush remnant, strip filler, then speak
            safe_tail = voice_boundary.finish()
            log_diagnostics(self.logger, voice_boundary.diagnostics)
            last_chunk = chunker.feed(safe_tail) if safe_tail else None
            remaining = chunker.flush()
            final_remainder = " ".join(part for part in (last_chunk, remaining) if part)
            final_text = (pending_chunk or "") + (" " + final_remainder if final_remainder else "")

            if final_text.strip():
                if not first_chunk_checked:
                    quality_issue = self.llm._check_response_quality(final_text, command)
                    if quality_issue:
                        self.logger.warning(
                            "Streaming quality gate failed (%s, response length=%d); "
                            "falling back to sync chat()",
                            quality_issue, len(final_text),
                        )
                        if audio_pipeline:
                            audio_pipeline.finish()
                        return self.llm.chat(
                            user_message=command,
                            conversation_history=history,
                            memory_context=memory_context,
                            conversation_messages=conversation_messages,
                            guest_mode=guest_mode,
                        )
                final_text = self.llm.strip_filler(self.llm.strip_metric(final_text, command))
                if final_text.strip():
                    # Append honorific to last chunk if LLM omitted it
                    from core.honorific import get_honorific, get_formal_address
                    h = get_honorific()
                    formal = get_formal_address()
                    combined_lower = (full_response + " " + final_text).lower()
                    honorific_present = (
                        (h and h.lower() in combined_lower)
                        or (formal and formal.lower() in combined_lower)
                    )
                    if h and not honorific_present:
                        final_text = final_text.rstrip().rstrip('.!?') + f" {h}."
                        full_response = full_response.rstrip().rstrip('.!?') + f" {h}."

                    if audio_pipeline:
                        audio_pipeline.put(final_text)
                    else:
                        self._speak_and_wait(final_text)
                    chunks_spoken += 1

            # Wait for all audio to finish playing
            if audio_pipeline:
                audio_pipeline.finish()

        except Exception as e:
            if self._turn_cancelled.is_set():
                if ack_timer:
                    ack_timer.cancel()
                if audio_pipeline:
                    audio_pipeline.cancel()
                return ""
            self.logger.error(f"Streaming LLM error: {e}")
            self._llm_responded = True
            if ack_timer:
                ack_timer.cancel()
            if audio_pipeline:
                audio_pipeline.finish()
            if not full_response:
                return self.llm.chat(
                    user_message=command,
                    conversation_history=history,
                    memory_context=memory_context,
                    conversation_messages=conversation_messages,
                    guest_mode=guest_mode,
                )

        # Cancel ack timer if stream was empty
        if self._turn_cancelled.is_set():
            return ""
        if not self._llm_responded:
            self._llm_responded = True
            if ack_timer:
                ack_timer.cancel()

        if chunks_spoken > 0:
            self.logger.info(f"Streamed LLM response in {chunks_spoken} chunks")
            self.tts._spoke = True
        self._active_audio_pipeline = None

        # Extended conversation window after research answers
        if tool_call_request:
            self.conversation.request_follow_up = 15.0
            # Store the exchange so follow-ups have context.
            # Use raw_command (not the augmented command) to prevent nested
            # context wrapping on successive follow-ups.
            self.conv_state.set_research_context(
                results=self.conv_state.research_results or [],
                exchange={"query": raw_command, "answer": full_response},
            )

            # Persist interaction for cross-session awareness
            if hasattr(self, 'memory_manager') and self.memory_manager:
                _uid = getattr(self.conversation, 'current_user', None) or 'christopher'
                tool_name = tool_call_request.name
                if tool_name == "web_search":
                    search_query = tool_call_request.arguments.get("query", raw_command)
                    result_urls = [
                        {"title": r.get("title", ""), "url": r.get("url", "")}
                        for r in (self.conv_state.research_results or [])
                    ]
                    self.memory_manager.persist_interaction(
                        "research", raw_command, full_response,
                        detail=search_query,
                        metadata={"result_urls": result_urls},
                        user_id=_uid,
                    )
                else:
                    self.memory_manager.persist_interaction(
                        "tool_call", raw_command, full_response,
                        detail=tool_name,
                        metadata={"tool_args": tool_call_request.arguments},
                        user_id=_uid,
                    )
        else:
            # Log pure LLM conversation for proactive surfacing
            if hasattr(self, 'memory_manager') and self.memory_manager and full_response:
                _uid = getattr(self.conversation, 'current_user', None) or 'christopher'
                self.memory_manager.persist_interaction(
                    "conversation", raw_command, full_response,
                    user_id=_uid,
                )

        return full_response

    def _process_speech_chunk(self, chunk, command, history, memory_context,
                              conversation_messages, chunks_spoken,
                              first_chunk_checked, pending_chunk,
                              audio_pipeline, use_pipeline):
        """Process a completed sentence chunk for speech.

        Returns updated (chunks_spoken, first_chunk_checked, pending_chunk, audio_pipeline).
        On quality gate failure, returns (-1, ..., fallback_response, ...).
        """
        if not first_chunk_checked:
            first_chunk_checked = True
            quality_issue = self.llm._check_response_quality(chunk, command)
            if quality_issue:
                self.logger.warning(
                    f"Streaming quality gate failed ({quality_issue}): "
                    f"'{chunk[:60]}' — falling back to sync chat()"
                )
                fallback = self.llm.chat(
                    user_message=command,
                    conversation_history=history,
                    memory_context=memory_context,
                    conversation_messages=conversation_messages,
                    guest_mode=getattr(self.conversation, 'current_user', None) == '__guest__',
                )
                return -1, first_chunk_checked, fallback, audio_pipeline

        if chunks_spoken == 0 and pending_chunk is None:
            # First chunk — strip redundant opener if ack already played
            if self.tts.ack_played:
                chunk = self._strip_ack_opener(chunk)
                self.tts.clear_ack_played()
                if not chunk:
                    return chunks_spoken, first_chunk_checked, pending_chunk, audio_pipeline
            processed = self.llm.strip_metric(chunk, command)
            self.listener.speaking = True
            if use_pipeline:
                _latency = self._current_latency
                audio_pipeline = StreamingAudioPipeline(
                    self.tts, self.logger,
                    on_first_audio=(
                        (lambda: _latency.mark("tts_first_pcm")) if _latency else None
                    ),
                )
                audio_pipeline.start()
                audio_pipeline.put(processed)
                self._active_audio_pipeline = audio_pipeline
            else:
                self._speak_and_wait(processed)
            chunks_spoken += 1
        else:
            # Buffer subsequent chunks; submit the previous one
            if pending_chunk:
                processed = self.llm.strip_metric(pending_chunk, command)
                if audio_pipeline:
                    audio_pipeline.put(processed)
                else:
                    self._speak_and_wait(processed)
                chunks_spoken += 1
            pending_chunk = chunk

        return chunks_spoken, first_chunk_checked, pending_chunk, audio_pipeline

    # ----- TTS helpers -----

    def _speak_and_wait(self, text: str):
        """Speak text synchronously (blocks until playback finishes).

        For the coordinator thread this is fine — we don't need to process
        other events while speaking a response to the current command.
        """
        self.listener.speaking = True
        self.listener.active_tts_text = text
        self.tts.speak(text)

    def handle_barge_in(self, text: str, speaker_id=None,
                        speaker_confidence: float = 0.0) -> bool:
        """Cancel an active response for a wake-word command or bare stop."""
        if not (self.listener._speaking_event.is_set() and self._barge_in_lock.acquire(blocking=False)):
            return False
        try:
            if self._turn_cancelled.is_set():
                return False
            words = re.findall(r"[\w']+", text.lower())
            stop_words = {"stopp", "stop", "halt"}
            aliases = {
                "jarvis", "jarwis", "jarwiss", "charvis", "charwis",
                "chauvis", "chauwis", "scharvis", "djarvis", "dscharvis",
                "tscharvis", self.wake_word,
            }
            wake_index = next((i for i, word in enumerate(words)
                               if max(SequenceMatcher(None, alias, word).ratio()
                                      for alias in aliases) >= 0.80), None)
            remaining = [word for i, word in enumerate(words) if i != wake_index]
            stop_only = bool(remaining) and all(
                word in stop_words | {"bitte", "please"} for word in remaining
            )
            stop_only = stop_only or (len(words) == 1 and words[0] in stop_words)
            if not stop_only and (wake_index is None or wake_index == len(words) - 1):
                return False

            transcript = " ".join(words)
            response_text = getattr(self.listener, "active_tts_text", "") or self._active_response_text
            response_words = re.findall(r"[\w']+", response_text.lower())
            if transcript:
                lower_bound = max(1, len(words) - 1)
                upper_bound = min(len(response_words), len(words) + 1)
                for window_size in range(lower_bound, upper_bound + 1):
                    for start in range(len(response_words) - window_size + 1):
                        echoed_text = " ".join(response_words[start:start + window_size])
                        if SequenceMatcher(None, transcript, echoed_text).ratio() >= 0.84:
                            return False

            self._turn_cancelled.set()
            self._llm_responded = True
            pipeline = self._active_audio_pipeline
            if pipeline is not None:
                pipeline.cancel()
            if hasattr(self.tts, "interrupt_active"):
                self.tts.interrupt_active()
            else:
                self.tts.kill_active()
            cancel_stream = getattr(self.llm, "cancel_active_stream", None)
            if callable(cancel_stream):
                cancel_stream()
            invalidate_audio = getattr(self.listener, "invalidate_pending_audio", None)
            if callable(invalidate_audio):
                invalidate_audio()
            if stop_only:
                self._stop_only_interrupt = True
            else:
                self.event_queue.put(Event(
                    EventType.TRANSCRIPTION_READY,
                    data={
                        "text": text.strip(),
                        "speaker_id": speaker_id,
                        "speaker_confidence": speaker_confidence,
                        "capture_generation": self.listener._capture_generation,
                        "barge_in": True,
                    },
                    source="barge_in",
                ))
            self.logger.info("Accepted voice interrupt; stopped current response")
            return True
        finally:
            self._barge_in_lock.release()

    # ----- direct audio (Gemma PRIMARY) -----

    def _content_logging_allowed(self) -> bool:
        try:
            from core.privacy_gate import Capability, get_privacy_gate
            return bool(get_privacy_gate(self.config).allow(Capability.CONTENT_LOGGING))
        except Exception:
            return False

    def _text_fallback_available(self) -> bool:
        """A text fallback exists only when explicitly enabled and configured."""
        if not self.config.get("llm.primary.text_fallback", False):
            return False
        if not self.config.get("llm.api.enabled", False):
            return False
        provider = str(self.config.get("llm.api.provider") or "").strip().lower()
        if provider not in {"openrouter", "anthropic"}:
            return False
        if not self.config.get("llm.api.model"):
            return False
        if provider == "openrouter" and not self.config.get("llm.api.endpoint"):
            return False
        env = self.config.get("llm.api.api_key_env")
        if not env or not _cloud_credential_matches_provider(provider, env):
            return False
        gate = getattr(self, "_privacy_gate", None)
        if gate is None:
            return False
        try:
            from core.privacy_gate import Capability
            if not gate.allow(Capability.CLOUD_LLM):
                return False
            key = self.config.get_env(env)
        except Exception:
            return False
        return bool(key) and not str(key).lower().startswith("your_")

    def _direct_audio_context(self, at, final: bool = False) -> dict:
        """Context for a direct-audio request.

        Start time (STT thread, before speaker resolution): strictly read-only,
        history only, no router state. ``final=True`` runs on the coordinator
        thread after the speaker was applied (only when the guest flag changed
        and the request has to be restarted): full router context for owners.
        Guests never get personal history/memory. Tools: ``llm.primary.audio_tools``
        (default ``none``; ``always`` / ``all`` opt in).
        """
        guest = getattr(self.conversation, "current_user", None) == "__guest__"
        ctx = {"guest_mode": guest, "history": "", "memory_context": None,
               "conversation_messages": None, "tools": None}
        if not guest:
            try:
                if final:
                    prepared = self.router._prepare_llm_context(
                        at.placeholder, in_conversation=bool(at.in_conversation))
                    ctx["history"] = prepared.llm_history
                    ctx["memory_context"] = prepared.memory_context
                    ctx["conversation_messages"] = prepared.context_messages
                else:
                    ctx["history"] = self.conversation.format_history_for_llm(
                        include_system_prompt=False)
            except Exception as exc:
                self.logger.debug("direct audio context fallback: %s", type(exc).__name__)
        mode = str(self.config.get("llm.primary.audio_tools", "none") or "none").lower()
        if mode in ("always", "all"):
            try:
                from core.tool_registry import ALL_TOOLS, ALWAYS_INCLUDED_TOOLS
                source = ALWAYS_INCLUDED_TOOLS if mode == "always" else ALL_TOOLS
                tools = list(source.values())
                try:
                    from core.tools.delegate_to_expert import is_available as _expert_ok
                    if not _expert_ok():
                        tools = [t for t in tools
                                 if t["function"]["name"] != "delegate_to_expert"]
                except Exception:
                    tools = [t for t in tools
                             if t["function"]["name"] != "delegate_to_expert"]
                if guest:
                    tools = [t for t in tools
                             if t["function"]["name"] in {"get_weather", "web_search"}]
                ctx["tools"] = tools or None
            except Exception:
                ctx["tools"] = None
        return ctx

    def _direct_route_result(self, direct) -> RouteResult:
        ctx = direct.context or {}
        from core.direct_audio import AUDIO_TURN_PROMPT
        return RouteResult(
            handled=False, intent="direct_audio", used_llm=True,
            llm_command=AUDIO_TURN_PROMPT,
            llm_history=ctx.get("history") or "",
            memory_context=ctx.get("memory_context"),
            context_messages=ctx.get("conversation_messages"),
            use_tools=ctx.get("tools"),
            tool_temperature=0.0,
            match_info={"layer": "direct_audio", "skill_name": "primary"},
        )

    def start_direct_audio_turn(self, audio, generation=None):
        """STTWorker hook: start the primary-model request for this audio now."""
        at = self.direct_audio.start_turn(
            audio, generation,
            in_conversation=bool(self.listener.conversation_window_active),
        )
        if at is not None and at.mode == "wait":
            self.logger.warning("Primary LLM %s - turn queued, no fallback configured",
                                self.direct_audio.status)
            print("⏳ Primärmodell startet (STARTING) - Anfrage wartet")
        return at

    def reject_audio_turn(self, turn_id, reason: str = "") -> bool:
        """No wake evidence / stale / noise: cancel the speculative request and
        discard its buffer. Ignored for turns without a gate (conversation window)."""
        if turn_id is None:
            return False
        at = self.direct_audio.get(turn_id)
        if at is None or not at.gate_required:
            return False
        rejected = at.turn.reject()
        if rejected:
            self.direct_audio.pop(turn_id)
            self.logger.info("Speculative direct-audio turn rejected (%s)", reason or "no wake")
        return rejected

    def cancel_audio_turn(self, turn_id, reason: str = "") -> bool:
        """STTWorker hook (privacy/stale): cancel a turn of ANY gate, running or queued."""
        if turn_id is None:
            return False
        cancelled = self.direct_audio.cancel_turn(turn_id)
        if cancelled:
            self.logger.info("Direct-audio turn cancelled (%s)", reason or "cancel")
        return cancelled

    # ----- direct-audio verdict (STT transcript as parallel helper) -----

    def _direct_turn_decision(self, at, raw_text):
        """Pure decision from the STT transcript: (action, command, reason).

        action: direct (Gemma answers), text (skill/tool/canned -> text pipeline),
        greeting (bare wake word) or reject (blank/annotation/garbage/noise).
        Never routes, never executes anything, never mutates router state.
        """
        text = (raw_text or "").strip()
        low = text.lower()
        if not low:
            return "reject", "", "blank"
        if (low.startswith('(') and low.endswith(')')) or \
           (low.startswith('[') and low.endswith(']')):
            return "reject", "", "noise"
        if is_garbage_transcription(low):
            return "reject", "", "garbage"
        low = self._apply_transcription_corrections(low)
        if not at.gate_required and self._is_conversation_noise(low):
            return "reject", "", "conversation_noise"
        from core.conversation_router import classify_text_path
        path, command, reason = classify_text_path(
            low, router=getattr(self, "router", None), in_conversation=bool(at.in_conversation),
            wake_word=self.wake_word)
        return path, command, reason

    def resolve_ungated_audio_turn(self, at, text, reason: str = "") -> None:
        """STTWorker hook (STT thread): verdict for a held conversation-window turn.

        text=None: no transcript. blank/stale/stop -> reject (no answer);
        an STT error releases the direct answer (STT is only a helper)."""
        if at is None or not at.hold_for_verdict or at.gate_required:
            return
        if text is None:
            if reason in ("blank", "stale", "stop"):
                self.direct_audio.set_verdict(at, "reject", "", reason)
            else:
                self.direct_audio.set_verdict(at, "direct", "", reason or "no_transcript")
            return
        self.direct_audio.note_transcript(at.turn_id, text)   # asr_hint (content gate inside)
        action, command, why = self._direct_turn_decision(at, text)
        if action == "reject":
            self.logger.info("Direct-audio turn rejected by STT verdict (%s)", why)
        self.direct_audio.set_verdict(at, action, command, why)

    def _divert_audio_turn_to_text(self, at, command: str, reason: str) -> None:
        """Gated turn whose transcript needs the text pipeline / is a bare wake:
        drop the (never released) speculative request and run the text path."""
        at.turn.reject()
        self.direct_audio.pop(at.turn_id)
        self.logger.info("Direct-audio turn diverted to text path (%s)", reason)
        self.event_queue.put(Event(
            EventType.COMMAND_DETECTED,
            data=command or "jarvis_only",
            source="coordinator",
        ))

    def _resolve_direct_turn_from_transcript(self, turn_id, text: str) -> bool:
        """Apply the parallel STT result to a direct-audio turn.

        Returns True when the transcript was fully consumed (caller returns).
        """
        at = self.direct_audio.get(turn_id)
        if at is None:
            return False
        self.direct_audio.note_transcript(turn_id, text)   # asr_hint metadata only
        if not at.gate_required:
            return True     # command already dispatched by the STT worker
        wake_match = find_wake_word(text, self.wake_word)
        if not wake_match:
            self.logger.info("No wake word detected (%d chars)", len(text))
            print("❌ No wake word (ignored)")
            self.reject_audio_turn(turn_id, "no_wake")
            return True
        _, _, matched_word, similarity = wake_match
        self.logger.info("Wake word detected (similarity: %.2f)", similarity)
        if self._is_ambient_wake_word(text, matched_word):
            print("🔇 Ambient mention (ignored)")
            self.reject_audio_turn(turn_id, "ambient")
            return True
        action, command, why = self._direct_turn_decision(at, text)
        if action == "reject":
            self.reject_audio_turn(turn_id, why)
            return True
        if action in ("greeting", "text"):
            # A bare wake word never goes to Gemma; tool/skill turns use the text path.
            self._divert_audio_turn_to_text(at, command, why)
            return True
        if at.turn.confirm_wake():
            self.event_queue.put(Event(
                EventType.COMMAND_DETECTED,
                data={"direct_audio_turn": turn_id},
                source="coordinator",
            ))
        return True

    def _await_direct_verdict(self, direct):
        """Consumer side of the verdict: ('direct'|'text'|'abort', command)."""
        if direct.hold_for_verdict and not direct.verdict_event.is_set():
            budget = self.direct_audio.verdict_timeout_s + 2.0
            if not direct.verdict_event.wait(timeout=budget):
                self.direct_audio.set_verdict(direct, "direct", "", "wait_timeout")
        if direct.turn.is_rejected and not direct.superseded:
            return "abort", ""
        if direct.superseded:
            return "text", direct.verdict_command or "jarvis_only"
        return "direct", ""

    def _finalize_direct_context(self, direct) -> None:
        """Coordinator thread, after the speaker was applied: the request context
        must match the CURRENT speaker (guest vs. owner), never the previous one."""
        if direct.speaker_resolved:
            self._apply_speaker_context(direct.speaker_id, direct.speaker_confidence)
        guest = getattr(self.conversation, "current_user", None) == "__guest__"
        if guest == bool((direct.context or {}).get("guest_mode", False)):
            return
        ctx = self._direct_audio_context(direct, final=True)
        if self.direct_audio.restart_turn(direct, ctx):
            self.logger.info("Direct-audio request restarted for the identified speaker")

    def _privacy_flush_direct_audio(self):
        """Privacy flush: cancel open AND running turns, buffers, audio and hints."""
        try:
            dropped = self.direct_audio.discard_all()
            if dropped:
                self.logger.info("Privacy flush discarded %d direct-audio turn(s)", dropped)
                if getattr(self, "state", None) == PipelineState.PROCESSING_COMMAND:
                    self._turn_cancelled.set()
                    self._llm_responded = True
                cancel_stream = getattr(self.llm, "cancel_active_stream", None)
                if callable(cancel_stream):
                    cancel_stream()
        except Exception:
            self.logger.debug("direct audio flush failed", exc_info=True)

    # ----- Primary <-> Expert handover wiring -----

    def attach_handover(self, handover) -> None:
        """Register the handover and the ``delegate_to_expert`` delegator (None clears it)."""
        self.handover = handover
        from core.tools.delegate_to_expert import set_expert_delegator
        if handover is None:
            set_expert_delegator(None)
            return
        set_expert_delegator(self._delegate_expert, available=self._expert_available)

    def _expert_available(self) -> bool:
        if getattr(self, "handover", None) is None:
            return False
        try:
            self.llm.resolve_role("expert")   # raises ValueError without llm.expert.endpoint
        except Exception:
            return False
        return True

    @staticmethod
    def _expert_request_from_route(command: str, result):
        from core.tools.delegate_to_expert import ExpertRequest
        return ExpertRequest(
            reason="explicit_user_request",
            task=(getattr(result, "llm_command", None) or command),
            original_user_intent=command,
        )

    def _delegate_expert(self, request) -> dict:
        """delegate_to_expert tool: the handover runs once the primary's turn is over."""
        if not self._expert_available():
            return {"accepted": False, "message": "Der Experte ist derzeit nicht verfügbar."}
        self._pending_expert = request
        return {"accepted": True,
                "message": "Ich befrage den Experten; das dauert einen Moment."}

    def _snapshot_conversation_state(self) -> dict:
        import copy
        return {"conv_state": copy.copy(self.conv_state),
                "history": list(getattr(self.conversation, "session_history", []) or [])}

    def _restore_conversation_state(self, snapshot) -> None:
        """Runs after the primary is back. The process kept the state, so this only repairs
        loss; the expert answer stored in the meantime is never overwritten."""
        if not snapshot:
            return
        history = getattr(self.conversation, "session_history", None)
        saved = snapshot.get("history") or []
        if history is not None and len(history) < len(saved):
            history[:] = saved + [m for m in history if m not in saved]
        if getattr(self, "conv_state", None) is None:
            self.conv_state = snapshot["conv_state"]

    def _run_expert_turn(self, request, in_conversation: bool = False, route=None) -> str:
        """One expert turn: handover -> expert answers under the JARVIS system prompt ->
        answer goes DIRECTLY to output/TTS (no primary pass) -> primary restores in background."""
        handover = getattr(self, "handover", None)
        if handover is None:
            msg = "Der Experte ist derzeit nicht verfügbar."
            self._speak_and_wait(msg)
            return msg
        guest = getattr(self.conversation, "current_user", None) == "__guest__"

        def call_expert(req):
            history = getattr(route, "llm_history", None) if route is not None else None
            if history is None:
                history = self.conversation.format_history_for_llm(include_system_prompt=False)
            return self.llm.chat(
                user_message=req.task, conversation_history=history or "",
                memory_context=(getattr(route, "memory_context", None) if route is not None else None),
                conversation_messages=(getattr(route, "context_messages", None)
                                       if route is not None else None),
                guest_mode=guest, role="expert")

        self._speak_and_wait("Einen Moment, ich hole den Experten.")
        res = handover.run_expert(request, call_expert,
                                  save_state=self._snapshot_conversation_state,
                                  restore_state=self._restore_conversation_state)
        answer = res.answer if res.ok else None
        if isinstance(answer, str) and answer.strip():
            return self.deliver_expert_answer(answer, {
                "command": getattr(request, "original_user_intent", "") or request.task,
                "in_conversation": in_conversation})
        self.logger.warning("Expert turn failed: %s", res.error)
        if self._turn_cancelled.is_set():
            return ""
        msg = "Der Experte konnte nicht antworten. Das Hauptmodell wird wieder gestartet."
        self._speak_and_wait(msg)
        self.conversation.add_message("assistant", msg, client_id="voice")
        return msg

    def _await_primary(self):
        """Before a normal primary LLM call: honest STARTING + queue while the primary reloads.

        Returns None to proceed (primary READY, or a real configured fallback), or a short
        message when the primary stayed unavailable for the whole queue window."""
        handover = getattr(self, "handover", None)
        if handover is None:
            return None
        if not handover.is_swapping and handover.primary_ready:
            return None
        timeout = float(self.config.get("handover.queue_wait_s", 120) or 0)
        now = time.monotonic()
        if now - getattr(self, "_starting_notice_ts", 0.0) > 30.0:
            self._starting_notice_ts = now
            self.logger.warning("Primary LLM not READY (%s) - request queued", handover.lifecycle_state())
            print("⏳ Primärmodell startet (STARTING) - Anfrage wartet")
            self._speak_and_wait("Das Sprachmodell wird gerade geladen. Ich antworte gleich.")
        decision = handover.resolve_provider(timeout)
        if decision.provider in ("primary", "fallback"):
            return None
        return "Das Sprachmodell ist noch nicht bereit. Bitte gleich noch einmal."

    # ----- stop fast path (outside TTS) -----

    _STOP_WORDS = {"stopp", "stop", "halt"}

    def _is_stop_only_transcript(self, text: str) -> bool:
        words = re.findall(r"[\w']+", (text or "").lower())
        if not words:
            return False
        aliases = {"jarvis", "jarwis", "jarwiss", "charvis", "charwis", "chauvis", "chauwis",
                   "scharvis", "djarvis", "dscharvis", "tscharvis", self.wake_word}
        wake_index = next((i for i, w in enumerate(words)
                           if max(SequenceMatcher(None, a, w).ratio() for a in aliases) >= 0.80), None)
        remaining = [w for i, w in enumerate(words) if i != wake_index]
        return bool(remaining) and all(w in self._STOP_WORDS | {"bitte", "please"} for w in remaining)

    def handle_stop_only(self, text: str, audio_turn=None) -> bool:
        """STTWorker hook for transcripts outside TTS. A stop-only command cancels any
        running/speculative primary turn, drops held aggregated audio and creates NO new
        LLM turn; TTS is interrupted as in the barge-in path. Returns True when consumed."""
        if not self._is_stop_only_transcript(text):
            return False
        speaking = getattr(self.listener, "_speaking_event", None)
        if speaking is not None and speaking.is_set():
            return False   # during TTS handle_barge_in owns the stop
        direct_audio = getattr(self, "direct_audio", None)
        # No ambient 'stop': only with the wake word, inside an active conversation
        # window or while a turn of ours is actually running/queued.
        own_id = getattr(audio_turn, "turn_id", None)
        other_turns = False
        if direct_audio is not None:
            try:
                with direct_audio._lock:
                    other_turns = any(tid != own_id for tid in
                                      list(direct_audio._turns) + list(direct_audio._active))
            except Exception:
                other_turns = False
        running = (getattr(self, "state", None) == PipelineState.PROCESSING_COMMAND
                   or bool(getattr(self, "_streaming_active", False)) or other_turns)
        if not (find_wake_word(text, self.wake_word)
                or getattr(self.listener, "conversation_window_active", False)
                or running):
            return False
        if direct_audio is not None:
            direct_audio.discard_all()          # cancels speculative + running direct turns
        if getattr(self, "state", None) == PipelineState.PROCESSING_COMMAND:
            self._turn_cancelled.set()
            self._llm_responded = True
            self._stop_only_interrupt = True
            pipeline = getattr(self, "_active_audio_pipeline", None)
            if pipeline is not None:
                pipeline.cancel()
        if hasattr(self.tts, "interrupt_active"):
            self.tts.interrupt_active()
        elif hasattr(self.tts, "kill_active"):
            self.tts.kill_active()
        cancel_stream = getattr(self.llm, "cancel_active_stream", None)
        if callable(cancel_stream):
            cancel_stream()
        discard = getattr(self.listener, "discard_held_turn", None)
        if callable(discard):
            discard()
        self.logger.info("Stop-only command outside TTS: turn cancelled, no new LLM turn")
        return True

    def deliver_expert_answer(self, text: str, turn_ctx: dict = None) -> str:
        """Deliver an EXPERT (Qwen) answer through the normal output path.

        Called by expert delegation (core/model_handover.py) with the answer the
        expert generated under the JARVIS system prompt (llm.chat/stream with
        role='expert'). There is NO second primary pass: the text is stored in
        the conversation state and pushed into the existing TTS/output path.

        turn_ctx (all optional): {"command": str, "in_conversation": bool,
                                  "audio_turn_id": str, "spoken": bool}
        """
        turn_ctx = turn_ctx or {}
        text = (text or "").strip()
        if not text:
            return ""
        command = turn_ctx.get("command") or ""
        stored = self.llm.strip_filler(self.llm.strip_metric(text, command))
        self.conversation.add_message("assistant", stored, client_id="voice")
        print(f"💬 Jarvis (Experte): {stored}")
        if not turn_ctx.get("spoken") and not self._turn_cancelled.is_set():
            self._speak_and_wait(stored)
        self.conv_state.update(command=command, response_text=stored,
                               response_type="expert")
        try:
            self._manage_conversation_window(
                stored, bool(turn_ctx.get("in_conversation", False)))
        except Exception:
            self.logger.debug("expert answer window management failed", exc_info=True)
        return stored

    def _finish_cancelled_turn(self):
        """Restore turn state after its queued barge-in transcript is safe."""
        pipeline = self._active_audio_pipeline
        if pipeline is not None:
            pipeline.cancel()
            if pipeline._thread is not None and pipeline._thread.is_alive():
                self._retired_audio_pipelines.append(pipeline)
        self._active_audio_pipeline = None
        self._active_response_text = ""
        self._streaming_active = False
        self._pending_expert = None
        self.listener.resume_listening()
        if getattr(self, "_stop_only_interrupt", False):
            self.listener.open_conversation_window(self.listener._extended_duration)
            self._stop_only_interrupt = False
        self.state = PipelineState.IDLE
        self._last_command_end_ts = self._last_idle_ts = time.monotonic()
        self._turn_cancelled.clear()

    # Regex to strip redundant LLM opening phrases when ack already played
    _ACK_OPENER_RE = re.compile(
        r'^(Certainly|Of course|Very well|Right away|One moment|Just a moment|'
        r'Give me (?:just )?a moment|Absolutely|Sure thing|One second)'
        r'[,.]?\s*(?:sir|ma\'am|miss)?\.?\s*',
        re.IGNORECASE,
    )

    @staticmethod
    def _classify_ack_style(command: str) -> str:
        """Classify query into an ack style for contextual acknowledgments.

        Legacy wrapper — use _classify_ack() for new code.
        """
        style, _ = Coordinator._classify_ack(command)
        return style

    @staticmethod
    def _classify_ack(command: str, in_conversation: bool = False,
                      jarvis_asked_question: bool = False) -> tuple:
        """Classify query style and decide whether to suppress the ack.

        Returns:
            (style: str, suppress: bool)
            style — one of "research", "checking", "working", "neutral"
            suppress — True if the ack should be skipped entirely
        """
        cl = command.lower().strip()
        word_count = len(cl.split())

        # --- Classify style ---
        # Research / current events
        if any(w in cl for w in ("search", "look up", "find out", "latest", "current", "news about")):
            style = "research"
        # Factual lookup
        elif any(cl.startswith(w) for w in (
            "what ", "who ", "when ", "where ", "how many ", "how much ", "is ", "are ", "was ", "does ",
        )):
            style = "checking"
        # Complex / explanatory
        elif any(cl.startswith(w) for w in (
            "explain ", "tell me about ", "describe ", "compare ", "why ", "how do ", "how does ",
        )):
            style = "working"
        else:
            style = "neutral"

        # --- Suppression rules ---
        # NEVER suppress research or working/complex queries — they benefit from acks
        if style in ("research", "working"):
            return style, False

        # Very short query (<=5 words) — likely conversational, Qwen responds fast
        if word_count <= 5:
            return style, True

        # JARVIS just asked a question and user is answering — no ack needed
        if jarvis_asked_question:
            return style, True

        # In-conversation + short query (<=12 words) — fast follow-up
        if in_conversation and word_count <= 12:
            return style, True

        return style, False

    def _play_ack_if_still_thinking(self, style_hint: str = None):
        """Timer callback — plays ack if LLM hasn't responded yet.

        Prefers contextual ack (4B-generated) if ready. Falls back to
        generic cached ack if 4B hasn't finished or returned empty.
        """
        if not self._llm_responded:
            # Pause mic BEFORE playback to prevent speaker-to-mic bleed
            # (ack phrase picked up as a new user command).  The main response
            # flow calls listener.resume_listening() when fully done.
            self.listener.pause_listening()

            # Try contextual ack first (4B-generated, fired at command arrival).
            # This goes through the SAME tts.speak() the real response uses,
            # which for Chatterbox is a real GPU synthesis request that holds
            # _tts_lock — unlike the pre-cached fallback ack below. Two
            # guards keep it from delaying the real response beyond a fixed
            # budget: cancel_check re-checks _llm_responded once the lock is
            # actually acquired (closing the pre-lock race window), and
            # timeout_override caps how long the Chatterbox call itself may
            # run, instead of the full response-length timeout. See
            # TextToSpeech.speak()'s docstring.
            ctx_ack = getattr(self, '_contextual_ack_text', None)
            if ctx_ack and not self._llm_responded:
                self.logger.info(f"Contextual ack: '{ctx_ack}'")
                played = self.tts.speak(
                    ctx_ack,
                    cancel_check=lambda: self._llm_responded,
                    timeout_override=self._CONTEXTUAL_ACK_TIMEOUT_S,
                )
                if played:
                    self.tts._ack_played = True
                return

            # Fallback: generic cached ack
            # Pass cancel_check so speak_ack rechecks after acquiring the
            # TTS lock — prevents stale acks when the response arrived
            # while this thread was blocked waiting for the lock.
            self.tts.speak_ack(
                style_hint=style_hint,
                cancel_check=lambda: self._llm_responded,
            )

    def _strip_ack_opener(self, text: str) -> str:
        """Strip leading ack phrase from LLM text if ack was already spoken."""
        stripped = self._ACK_OPENER_RE.sub('', text)
        if stripped != text:
            # Capitalize the new leading character
            stripped = stripped.lstrip()
            if stripped:
                stripped = stripped[0].upper() + stripped[1:]
            self.logger.info("Stripped acknowledgement opener (%d chars)", len(text))
        return stripped

    def _play_beep(self):
        """Play wake-word acknowledgment beep."""
        try:
            if not self.beep_path.exists():
                return
            import subprocess
            from core.tts import resolve_output_device
            audio_device = resolve_output_device(
                self.config.get("audio.output_device", "default")
            )
            subprocess.run(
                ["aplay", "-D", audio_device, str(self.beep_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
        except Exception as e:
            self.logger.error(f"Failed to play beep: {e}")

    # ----- conversation helpers -----

    def _handle_close_conversation(self, event: Event):
        """Handle explicit conversation window close + reset memory surfacing."""
        self.listener.close_conversation_window()
        if self.memory_manager:
            self.memory_manager.reset_surfacing_window()
        if self.awareness:
            self.awareness.reset_window()
        if self.context_window:
            self.context_window.reset()
        # Demote artifacts to warm tier, then promote to long-term memory
        if self.interaction_cache and self.conv_state.window_id:
            self.interaction_cache.demote_window(self.conv_state.window_id)
            self._promote_window_artifacts()
        # Reset centralized conversation state (clears research cache,
        # jarvis_asked_question, last intent/response tracking)
        self.conv_state.close_window()
        if self.web_researcher:
            self.web_researcher.clear_cache()

    def _on_conversation_timeout(self):
        """Cleanup when conversation window expires due to silence.

        Called by ContinuousListener.on_window_close callback.
        Same cleanup as _handle_close_conversation, but the listener already
        closed itself (flipped flag + played tone), so we skip that call.
        """
        self.logger.info("Timeout cleanup: resetting state, context, caches")
        if self.memory_manager:
            self.memory_manager.reset_surfacing_window()
        if self.awareness:
            self.awareness.reset_window()
        if self.context_window:
            self.context_window.reset()
        # Demote artifacts to warm tier, then promote to long-term memory
        if self.interaction_cache and self.conv_state.window_id:
            self.interaction_cache.demote_window(self.conv_state.window_id)
            self._promote_window_artifacts()
        self.conv_state.close_window()
        if self.web_researcher:
            self.web_researcher.clear_cache()

    def _promote_window_artifacts(self):
        """Promote meaningful artifacts to long-term memory in a background thread.

        Captures window state before close_window() clears it, then runs
        promotion + session summary persistence off the main thread.
        """
        if not self.interaction_cache or not self.memory_manager:
            return

        # Capture state before close_window() resets it
        window_id = self.conv_state.window_id
        user_id = (getattr(self.conversation, 'current_user', None)
                   or 'christopher')
        duration = 0.0
        if self.conv_state.window_opened_at:
            duration = time.time() - self.conv_state.window_opened_at

        cache = self.interaction_cache
        mm = self.memory_manager

        def _promote():
            try:
                artifacts = cache.promote_window(window_id)
                if artifacts:
                    mm.promote_session_artifacts(
                        artifacts, window_id,
                        duration_seconds=duration,
                        user_id=user_id,
                    )
                # CMA consolidation: scan cold tier for patterns
                cache.consolidate(user_id=user_id, memory_manager=mm)
            except Exception as e:
                cache.logger.warning(
                    "Background promotion failed for window %s: %s",
                    window_id, e,
                )

        threading.Thread(target=_promote, daemon=True).start()

    def _manage_conversation_window(self, response: str, was_in_conversation: bool):
        """Decide whether to open/extend the conversation window.

        Window duration adapts to conversation context:
        - Base: extended (7s) if follow-up invited, default (4s) otherwise
        - Active conversation bonus: 3+ turns → 50% extension
        - JARVIS asked a question → at least 10s for user to think
        """
        if self.conversation.should_open_follow_up_window(response):
            base = self.listener._extended_duration
        else:
            base = self.listener._default_duration

        # Active conversation bonus: 3+ turns → 50% extension
        if self.conv_state.turn_count >= 3:
            base *= 1.5

        # JARVIS asked a question → give user time to think
        if response and response.rstrip().endswith("?"):
            base = max(base, 10.0)

        self.listener.open_conversation_window(base)

    def _extract_command(self, full_text: str) -> str:
        """Extract command text from transcription (remove wake word)."""
        command = strip_wake_word(full_text, self.wake_word)
        return command or "jarvis_only"

    # ----- noise / correction helpers (from continuous_listener) -----

    def _is_conversation_noise(self, text: str) -> bool:
        """Check if text during conversation window is likely noise."""
        if len(text) < 2:
            return True
        unique_chars = set(text.replace(' ', ''))
        if len(unique_chars) <= 3 and len(text) > 5:
            return True
        words = text.strip().split()
        if len(words) == 1 and words[0] not in self._valid_short_replies:
            if len(words[0]) < 4:
                return True
        return False

    # Post-transcription word corrections for known Whisper mishearings.
    # Mirrors continuous_listener._TRANSCRIPTION_CORRECTIONS — keep in sync.
    _TRANSCRIPTION_CORRECTIONS = {
        "and videos": "amd's",
        "and video": "amd",
        "in video": "nvidia",
        "in vidya": "nvidia",
        "and vidya": "nvidia",
        "quinn": "qwen",
    }

    def _apply_transcription_corrections(self, text: str) -> str:
        """Fix known Whisper brand-name mishearings (AMD, NVIDIA, etc.)."""
        corrected = text
        for wrong, right in self._TRANSCRIPTION_CORRECTIONS.items():
            if wrong in corrected:
                corrected = corrected.replace(wrong, right)
        if corrected != text:
            self.logger.info("Applied transcription correction (%d chars)", len(text))
        return corrected

    def _apply_command_corrections(self, text: str) -> str:
        """Apply corrections for common command mishearings."""
        import re
        if re.match(r'^i (was|analyzed)\s+', text, re.IGNORECASE):
            return re.sub(r'^i (was|analyzed)\s+', 'analyze ', text, flags=re.IGNORECASE)
        return text

    # ----- ambient wake word filter -----

    # Words that follow "jarvis" in ambient speech (talking ABOUT jarvis)
    # but never follow "jarvis," in a command.
    _AMBIENT_FOLLOWERS = frozenset({
        'is', 'was', 'has', 'had', 'will', 'would', 'can', 'could',
        'does', 'did', 'should', 'might', 'may', 'of',
    })

    # Prefixes that legitimately precede the wake word (e.g. "hey jarvis")
    _WAKE_PREFIXES = frozenset({
        'hey', 'hi', 'yo', 'morning', 'good', 'okay', 'ok',
    })

    def _is_ambient_wake_word(self, text: str, matched_word: str) -> bool:
        """Determine if a wake word detection is ambient conversation, not a command.

        Uses position, post-wake-word analysis, and utterance length to
        distinguish "Jarvis, what time is it?" from "he was talking about Jarvis".

        Returns True if the wake word should be IGNORED (ambient).
        """
        words = text.split()

        # Find word index of the matched wake word
        word_idx = None
        for i, w in enumerate(words):
            if w.strip('.,!?;:\'"') == matched_word:
                word_idx = i
                break

        if word_idx is None:
            return False  # Can't determine — let it through

        # A comma-delimited middle vocative is an explicit invocation.
        if ((word_idx > 0 and words[word_idx - 1].endswith(","))
                or words[word_idx].endswith(",")):
            return False

        # --- Signal 1: Position ---
        # Real commands have "jarvis" at the start (first 2-3 words with
        # prefixes like "hey"/"good morning") OR at the end (trailing
        # address like "what time is it, jarvis?").
        # Ambient mentions are in the MIDDLE of longer sentences.
        effective_pos = word_idx
        if word_idx <= 2:
            # Check if earlier words are known prefixes
            prefix_words = [w.strip('.,!?;:') for w in words[:word_idx]]
            if all(pw in self._WAKE_PREFIXES for pw in prefix_words):
                effective_pos = 0  # Treat as position 0

        # Trailing wake word = command ("how are you, jarvis?")
        is_trailing = word_idx >= len(words) - 2  # last or second-to-last word

        if effective_pos >= 3 and not is_trailing:
            self.logger.info("Ambient speech rejected (wake word position=%d)", word_idx)
            return True

        # --- Signal 2: Post-wake-word copula/auxiliary ---
        # "jarvis is listening" = ambient.  "jarvis, is it raining?" = command.
        # The comma after "jarvis" is the key differentiator.
        if word_idx < len(words):
            wake_token = words[word_idx]  # e.g. "jarvis," or "jarvis" or "jarvis's"

            # Possessive = always ambient ("jarvis's brain")
            if wake_token.endswith("'s") or wake_token.endswith("\u2019s"):
                self.logger.info("Ambient speech rejected (possessive wake-word form)")
                return True

            has_comma = wake_token.endswith(',')
            if not has_comma and word_idx + 1 < len(words):
                next_word = words[word_idx + 1].strip('.,!?;:').lower()
                if next_word in self._AMBIENT_FOLLOWERS:
                    self.logger.info("Ambient speech rejected (wake word followed by ambient wording)")
                    return True

        # --- Signal 5: Length heuristic ---
        # Very long utterances where wake word isn't the opener are
        # almost certainly ambient conversation, not commands.
        if len(words) > 15 and word_idx > 0:
            self.logger.info(
                "Ambient speech rejected (word_count=%d wake_word_position=%d)",
                len(words), word_idx,
            )
            return True

        return False

    # ----- speaker context -----

    def _apply_speaker_context(self, speaker_id: Optional[str], confidence: float):
        """Set honorific and conversation user based on speaker identification."""
        primary_user_id = self.config.get("user_profiles.primary_user_id", "primary_user")
        single_user = self.config.get("user_profiles.single_user_mode", False)
        single_user_fallback = single_user and speaker_id in (None, "__guest__")
        if single_user_fallback:
            # Configured local mic context, not acoustic speaker verification.
            speaker_id = primary_user_id
            confidence = 0.0

        self._last_speaker_confidence = confidence
        effective_speaker_id = speaker_id or "__guest__"
        now = time.time()
        if (effective_speaker_id != "__guest__" and self._last_speaker_id
                and effective_speaker_id != self._last_speaker_id
                and self._last_speaker_id != "__guest__"
                and now - self._last_switch_time < 60):
            self._rapid_switch_count += 1
            self.logger.info(
                f"Speaker switch #{self._rapid_switch_count}: "
                f"{self._last_speaker_id} → {effective_speaker_id}"
            )
        elif effective_speaker_id != self._last_speaker_id:
            self._rapid_switch_count = (
                1 if (effective_speaker_id != "__guest__" and self._last_speaker_id
                      and self._last_speaker_id != "__guest__") else 0
            )
        self._last_switch_time = now
        self._last_speaker_id = effective_speaker_id
        if speaker_id == primary_user_id and self.profile_manager:
            honorific = self.profile_manager.get_honorific_for(speaker_id)
            formal = self.profile_manager.get_formal_address_for(speaker_id)
            set_honorific(honorific, formal)
            self.conversation.current_user = speaker_id
            if self.context_window:
                self.context_window.set_user(speaker_id)
            if single_user_fallback:
                self.logger.info(
                    "Primary local context: %s "
                    "(speaker_verification=not_performed, confidence=%.3f)",
                    speaker_id, confidence,
                )
            else:
                self.logger.info(
                    "Speaker profile matched: %s (confidence=%.3f)",
                    speaker_id, confidence,
                )
        elif (speaker_id and speaker_id != "__guest__" and self.profile_manager
              and self.profile_manager.get_profile(speaker_id)):
            honorific = self.profile_manager.get_honorific_for(speaker_id)
            formal = self.profile_manager.get_formal_address_for(speaker_id)
            set_honorific(honorific, formal)
            self.conversation.current_user = speaker_id
            if self.context_window:
                self.context_window.set_user(speaker_id)
            self.logger.info("Recognized profile context: %s", speaker_id)
        elif self.profile_manager:
            set_honorific("Gast")
            self.conversation.current_user = "__guest__"
            if self.context_window:
                self.context_window.set_user("__guest__")
            self.logger.info("Unknown speaker; personal context disabled (confidence=%.3f)", confidence)

    # ----- resume handler -----

    def _handle_resume(self, event: Event):
        """Handle RESUME_LISTENING — suppressed while streaming is active."""
        if self._streaming_active:
            self.logger.debug("Suppressing resume — streaming active")
            return
        self.listener.resume_listening()

    # ----- speech lifecycle -----

    def _handle_speech_started(self, event: Event):
        self.logger.debug("Speech started")

    def _handle_speech_finished(self, event: Event):
        self.logger.debug("Speech finished")

    # ----- LLM complete -----

    def _handle_llm_complete(self, event: Event):
        """Handle LLM streaming completion."""
        self._streaming_active = False
        self.logger.info("LLM streaming complete")

    # ----- error handling -----

    def _handle_error(self, event: Event):
        data = event.data or {}
        source = data.get("source", "unknown")
        error = data.get("error", "unknown error")
        self.logger.error(f"Pipeline error from {source}: {error}")

        self.stats['errors'] += 1
        self.stats['last_error_time'] = time.time()
        self.stats['last_error_msg'] = f"{source}: {error}"

        if source == "tts":
            # TTS failure — ensure listening resumes
            self.listener.resume_listening()

    # ----- metrics recording -----

    def _record_metrics(self, result: RouteResult, used_llm: bool,
                        elapsed_ms: float = None):
        """Record interaction metrics for ALL routes, not just LLM."""
        if not self.metrics:
            return
        try:
            info = self.llm.last_call_info or {} if used_llm else {}
            match_info = result.match_info or {}
            tools = getattr(self, '_last_tools_called', [])
            tools_str = ", ".join(tools) if tools else None
            # Route layer: prefer match_info, fall back to result.intent
            _route_layer = (match_info.get('layer')
                            or result.intent
                            or ('llm_fallback' if used_llm else 'unknown'))
            _latency = info.get('latency_ms') or elapsed_ms
            # Skill = actual handling skill, not available tools list
            _skill = None
            if match_info:
                _layer = match_info.get('layer', '')
                if 'CAL-L0' in _layer or 'cal_l0' in _layer:
                    _skill = 'conversation'
                elif 'P4' in _layer:
                    _skill = tools_str
                else:
                    _skill = match_info.get('skill_name')
            self.metrics.record(
                provider=info.get('provider', 'skill' if not used_llm else 'unknown'),
                method=info.get('method', result.source or 'handled'),
                prompt_tokens=info.get('input_tokens'),
                completion_tokens=info.get('output_tokens'),
                estimated_tokens=info.get('estimated_tokens'),
                model=info.get('model'),
                latency_ms=_latency,
                ttft_ms=info.get('ttft_ms'),
                skill=_skill,
                intent=result.intent or match_info.get('handler'),
                input_method='voice',
                quality_gate=info.get('quality_gate', False),
                is_fallback=info.get('is_fallback', False),
                error=info.get('error'),
                route_layer=_route_layer,
                tools_called=tools_str,
                session_id=getattr(result, 'trace_id', None),
                synthesis_category=getattr(result, 'synthesis_category', None),
            )
            self._last_tools_called = []
        except Exception as e:
            self.logger.error(f"Metrics recording failed: {e}")
