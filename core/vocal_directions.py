"""Internal vocal directions. Only explicit pause tags affect audio.

The streaming boundary buffer removes tag syntax before it reaches the speech
chunker. Private-use pause markers carry event order through sentence chunks;
they are consumed by ``parse_directions`` before any TTS engine sees text.
"""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Callable


PROBE_PAUSE_MS = {"short": 200, "medium": 500, "long": 1000}
UNSUPPORTED_EVENTS = frozenset({
    "breath", "inhale", "exhale", "yawn", "cough", "sneeze",
})
_MARKERS = {name: chr(0xE000 + index) for index, name in enumerate(PROBE_PAUSE_MS)}
_MARKER_NAMES = {marker: name for name, marker in _MARKERS.items()}
_TAG_PREFIX = "[voice"


@dataclass(frozen=True)
class PauseEvent:
    kind: str
    duration_ms: int


@dataclass(frozen=True)
class PcmChunk:
    data: bytes
    sample_rate: int
    channels: int = 1
    sample_width: int = 2
    encoding: str = "pcm_s16le"


@dataclass(frozen=True)
class DirectionDiagnostic:
    event_type: str
    status: str
    position: int


@dataclass(frozen=True)
class DirectionPlan:
    parts: tuple[str | PauseEvent, ...]
    diagnostics: tuple[DirectionDiagnostic, ...]

    @property
    def has_pause(self) -> bool:
        return any(isinstance(part, PauseEvent) for part in self.parts)

    @property
    def plain_text(self) -> str:
        return "".join(part for part in self.parts if isinstance(part, str))


class VoiceTagBoundaryBuffer:
    """Bounded incremental scanner for reserved ``[voice...]`` tags."""

    MAX_TAG_CHARS = 256

    def __init__(self):
        self._pending = ""
        self._state = "text"
        self._position = 0
        self._tag_start = 0
        self._join_left_word = False
        self._last_output = ""
        self.diagnostics: list[DirectionDiagnostic] = []

    def _append(self, out: list[str], value: str) -> None:
        if not value:
            return
        if self._join_left_word:
            if value[0].isalnum():
                out.append(" ")
            self._join_left_word = False
        out.append(value)
        self._last_output = value[-1]

    def _removed(self) -> None:
        self._join_left_word = self._join_left_word or self._last_output.isalnum()

    def _complete_tag(self, out: list[str]) -> None:
        body = self._pending[len("[voice:"):-1] if self._pending.startswith("[voice:") else ""
        position = self._tag_start
        if body.startswith("pause=") and body[6:] in _MARKERS:
            kind = body[6:]
            self.diagnostics.append(DirectionDiagnostic(f"pause:{kind}", "supported", position))
            self._join_left_word = False
            self._append(out, _MARKERS[kind])
        else:
            status = "unsupported" if body in UNSUPPORTED_EVENTS else "invalid"
            event_type = body if status == "unsupported" else (
                "pause" if body.startswith("pause=") else "unknown"
            )
            self.diagnostics.append(DirectionDiagnostic(event_type, status, position))
            self._removed()
        self._pending = ""
        self._state = "text"

    def feed(self, fragment: str) -> str:
        out: list[str] = []
        for char in fragment:
            position = self._position
            self._position += 1
            if self._state == "discard":
                if char == "]":
                    self._state = "text"
                    self._removed()
                continue
            if self._state == "text":
                if char == "[":
                    self._pending = char
                    self._tag_start = position
                    self._state = "candidate"
                else:
                    self._append(out, char)
                continue
            if self._state == "candidate":
                candidate = self._pending + char
                if _TAG_PREFIX.startswith(candidate):
                    self._pending = candidate
                elif self._pending == _TAG_PREFIX and (char in ":]" or char.isspace()):
                    self._pending = candidate
                    if char == "]":
                        self._complete_tag(out)
                    else:
                        self._state = "tag"
                else:
                    self._state = "text"
                    self._pending = ""
                    self._append(out, candidate)
                continue
            # Reserved tag: hold at most 256 characters, then discard until ].
            if len(self._pending) >= self.MAX_TAG_CHARS:
                self.diagnostics.append(DirectionDiagnostic("unknown", "overflow", self._tag_start))
                self._pending = ""
                self._state = "text" if char == "]" else "discard"
                if char == "]":
                    self._removed()
            elif char == "]":
                self._pending += char
                self._complete_tag(out)
            else:
                self._pending += char
        return "".join(out)

    def finish(self) -> str:
        out: list[str] = []
        if self._state == "candidate" and self._pending != _TAG_PREFIX:
            # Preserve ordinary bracket text, including an incomplete prefix
            # that never reached the reserved name.
            self._append(out, self._pending)
        elif self._state != "text":
            self.diagnostics.append(DirectionDiagnostic("unknown", "incomplete", self._tag_start))
            self._removed()
        self._pending = ""
        self._state = "text"
        return "".join(out)


def parse_directions(text: str, pause_ms: dict[str, int] | None = None) -> DirectionPlan:
    """Parse raw directions or already scanned streaming pause markers."""
    diagnostics: tuple[DirectionDiagnostic, ...] = ()
    if _TAG_PREFIX in text:
        scanner = VoiceTagBoundaryBuffer()
        text = scanner.feed(text) + scanner.finish()
        diagnostics = tuple(scanner.diagnostics)

    durations = pause_ms or PROBE_PAUSE_MS
    parts: list[str | PauseEvent] = []
    current: list[str] = []
    for char in text:
        kind = _MARKER_NAMES.get(char)
        if kind is None:
            current.append(char)
            continue
        if current:
            parts.append("".join(current))
            current.clear()
        parts.append(PauseEvent(kind, durations[kind]))
    if current:
        parts.append("".join(current))
    return DirectionPlan(tuple(parts), diagnostics)


def has_directions(text: str) -> bool:
    if any(marker in text for marker in _MARKER_NAMES):
        return True
    offset = 0
    while (index := text.find(_TAG_PREFIX, offset)) >= 0:
        end = index + len(_TAG_PREFIX)
        if end == len(text) or text[end] in ":]" or text[end].isspace():
            return True
        offset = end
    return False


def log_diagnostics(logger, diagnostics: tuple[DirectionDiagnostic, ...] | list[DirectionDiagnostic]) -> None:
    for item in diagnostics:
        logger.debug(
            "Voice direction event=%s status=%s position=%d",
            item.event_type, item.status, item.position,
        )


def resample_pcm_s16le(pcm: bytes, source_rate: int, target_rate: int) -> bytes:
    """Strict conversion for a mixed Chatterbox/Piper directed utterance."""
    if source_rate == target_rate:
        return pcm
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "s16le", "-ac", "1", "-ar", str(source_rate),
            "-i", "pipe:0", "-f", "s16le", "-ac", "1",
            "-ar", str(target_rate), "pipe:1",
        ],
        input=pcm, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=10, check=True,
    )
    if not result.stdout or len(result.stdout) % 2:
        raise ValueError("Directed PCM resampling produced invalid output")
    return result.stdout


def compose_directed_pcm(
    plan: DirectionPlan,
    synthesize: Callable[[str], PcmChunk | None],
    normalize: Callable[[str], str],
    *,
    default_rate: int | None = None,
    resample: Callable[[bytes, int, int], bytes] | None = None,
) -> tuple[bytes | None, int | None]:
    """Combine verified mono 16-bit PCM and exact-duration pause frames."""
    output: list[bytes | PauseEvent] = []
    rate: int | None = None
    audio_format: tuple[int, int, str] | None = None
    for part in plan.parts:
        if isinstance(part, PauseEvent):
            output.append(part)
            continue
        text = normalize(part)
        if not text.strip():
            continue
        chunk = synthesize(text)
        if chunk is None or not chunk.data or not chunk.sample_rate:
            return None, None
        segment_format = (chunk.channels, chunk.sample_width, chunk.encoding)
        if segment_format != (1, 2, "pcm_s16le"):
            raise ValueError("Unsupported directed PCM format")
        if audio_format is None:
            audio_format = segment_format
        elif audio_format != segment_format:
            raise ValueError("Directed PCM format mismatch")
        if len(chunk.data) % (chunk.channels * chunk.sample_width):
            raise ValueError("Misaligned directed PCM")
        if rate is None:
            rate = default_rate or chunk.sample_rate
        data = chunk.data
        if rate != chunk.sample_rate:
            if resample is None:
                raise ValueError("Directed PCM sample-rate mismatch")
            data = resample(data, chunk.sample_rate, rate)
            if not data or len(data) % (chunk.channels * chunk.sample_width):
                raise ValueError("Directed PCM resampling produced invalid output")
        output.append(data)
    if rate is None and any(isinstance(part, PauseEvent) for part in output):
        rate = default_rate
    if rate is None:
        return None, None

    pcm_parts = [
        b"\x00" * (rate * part.duration_ms // 1000 * 2)
        if isinstance(part, PauseEvent) else part
        for part in output
    ]
    return b"".join(pcm_parts), rate
