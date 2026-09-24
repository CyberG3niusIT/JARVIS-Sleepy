"""Behavioral tests for internal, non-spoken vocal directions."""

import pytest

from core.speech_chunker import SpeechChunker
from core.tts_normalizer_de import GermanTTSNormalizer
from core.vocal_directions import (
    PcmChunk, PauseEvent, VoiceTagBoundaryBuffer, compose_directed_pcm,
    has_directions, log_diagnostics, parse_directions,
)


def test_parser_keeps_german_text_and_natural_punctuation():
    plan = parse_directions("Äpfel, Öl und Grüße. [voice:pause=short]Weiter!")
    assert plan.parts == (
        "Äpfel, Öl und Grüße. ", PauseEvent("short", 200), "Weiter!",
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("[voice:pause=short]Hallo", (PauseEvent("short", 200), "Hallo")),
        ("Hallo[voice:pause=short]", ("Hallo", PauseEvent("short", 200))),
        (
            "Hallo[voice:pause=short][voice:pause=medium]Welt",
            ("Hallo", PauseEvent("short", 200), PauseEvent("medium", 500), "Welt"),
        ),
    ],
)
def test_pause_order_and_edges(source, expected):
    assert parse_directions(source).parts == expected


def test_unsupported_and_invalid_tags_do_not_split_or_join_words():
    plan = parse_directions("Hallo[voice:cough]Welt [voice:bogus]heute")
    assert plan.parts == ("Hallo Welt heute",)
    assert [(d.event_type, d.status) for d in plan.diagnostics] == [
        ("cough", "unsupported"), ("unknown", "invalid"),
    ]
    assert parse_directions("Hallo [voice:pause=huge]Welt").plain_text == "Hallo Welt"
    assert parse_directions("Hallo[voice:breath].").plain_text == "Hallo."
    assert parse_directions("Ein [normaler Hinweis] bleibt.").plain_text == "Ein [normaler Hinweis] bleibt."
    assert has_directions("Ein [voice-over] bleibt.") is False
    assert has_directions("Hallo[voice:pause=short]") is True


def test_unfinished_tag_is_removed():
    plan = parse_directions("Hallo[voice:pause=short")
    assert plan.plain_text == "Hallo"
    assert plan.diagnostics[0].status == "incomplete"


def test_streaming_boundary_spans_feed_calls_without_leaking_tag():
    boundary = VoiceTagBoundaryBuffer()
    chunker = SpeechChunker()
    emitted = []
    for token in ("Hallo, ", "Welt[vo", "ice:pause=short] ", "Weiter. "):
        safe = boundary.feed(token)
        assert "[voice" not in safe
        chunk = chunker.feed(safe) if safe else None
        if chunk:
            emitted.append(chunk)
    chunker.feed(boundary.finish())
    tail = chunker.flush()
    if tail:
        emitted.append(tail)
    assert all("[voice" not in chunk for chunk in emitted)
    plan = parse_directions(" ".join(emitted))
    assert plan.has_pause
    assert "Hallo, Welt" in plan.plain_text


def test_overflow_discards_tag_then_resumes_normal_text():
    boundary = VoiceTagBoundaryBuffer()
    output = boundary.feed("Hallo[voice:" + "x" * 300)
    assert output == "Hallo"
    output += boundary.feed("]Welt")
    output += boundary.finish()
    assert output == "Hallo Welt"
    assert [d.status for d in boundary.diagnostics] == ["overflow"]
    assert len(boundary._pending) <= boundary.MAX_TAG_CHARS


def test_boundary_buffer_never_holds_more_than_256_characters():
    boundary = VoiceTagBoundaryBuffer()
    assert boundary.feed("[voice:" + "x" * 249) == ""
    assert len(boundary._pending) == 256
    assert boundary.feed("]Danach") == "Danach"
    assert boundary.diagnostics[0].status == "overflow"


def test_missing_closer_never_releases_tag_body():
    boundary = VoiceTagBoundaryBuffer()
    assert boundary.feed("Hallo[voice:pause=short.") == "Hallo"
    assert boundary.finish() == ""
    assert boundary.diagnostics[0].status == "incomplete"


def test_pcm_leading_trailing_and_consecutive_pauses():
    plan = parse_directions(
        "[voice:pause=short]Hallo[voice:pause=short][voice:pause=medium]Welt"
        "[voice:pause=long]"
    )
    spoken = []

    def synthesize(text):
        spoken.append(text)
        return PcmChunk(b"\x01\x00" * 2, 24000)

    pcm, rate = compose_directed_pcm(plan, synthesize, str.strip)
    assert rate == 24000
    assert spoken == ["Hallo", "Welt"]
    assert pcm == (
        b"\x00" * (24000 * 200 // 1000 * 2)
        + b"\x01\x00" * 2
        + b"\x00" * (24000 * 700 // 1000 * 2)
        + b"\x01\x00" * 2
        + b"\x00" * (24000 * 1000 // 1000 * 2)
    )


@pytest.mark.parametrize(
    "bad_chunk",
    [
        PcmChunk(b"\x01\x00", 22050),
        PcmChunk(b"\x01\x00", 24000, channels=2),
        PcmChunk(b"\x01\x00", 24000, sample_width=1),
        PcmChunk(b"\x01\x00", 24000, encoding="pcm_f32le"),
    ],
)
def test_pcm_rejects_mismatched_rate_and_format(bad_chunk):
    plan = parse_directions("Hallo[voice:pause=short]Welt")
    chunks = iter((PcmChunk(b"\x01\x00", 24000), bad_chunk))
    with pytest.raises(ValueError):
        compose_directed_pcm(plan, lambda text: next(chunks), str.strip)


def test_pcm_resamples_only_rate_mismatch_when_requested():
    plan = parse_directions("Hallo[voice:pause=short]Welt")
    chunks = iter((PcmChunk(b"\x01\x00", 24000), PcmChunk(b"\x02\x00", 22050)))
    calls = []

    def resample(data, source_rate, target_rate):
        calls.append((source_rate, target_rate))
        return b"\x03\x00"

    pcm, rate = compose_directed_pcm(
        plan, lambda text: next(chunks), str.strip,
        default_rate=24000, resample=resample,
    )
    assert rate == 24000
    assert calls == [(22050, 24000)]
    assert pcm.endswith(b"\x03\x00")


def test_only_pause_without_text_uses_default_rate():
    plan = parse_directions("[voice:pause=short]")
    pcm, rate = compose_directed_pcm(
        plan, lambda text: pytest.fail("no synthesis expected"), str.strip,
        default_rate=24000,
    )
    assert rate == 24000
    assert len(pcm) == 24000 * 200 // 1000 * 2


def test_normalizer_receives_only_text_segments():
    plan = parse_directions("Es sind 42,[voice:pause=short] vielleicht 43.")
    spoken = []

    def synthesize(text):
        spoken.append(text)
        return PcmChunk(b"\x01\x00", 24000)

    compose_directed_pcm(plan, synthesize, GermanTTSNormalizer().normalize)
    assert spoken == ["Es sind zweiundvierzig,", "vielleicht dreiundvierzig."]


def test_diagnostics_do_not_log_unknown_tag_body():
    plan = parse_directions("Hallo[voice:private information]Welt")
    messages = []

    class Logger:
        def debug(self, template, *args):
            messages.append(template % args)

    log_diagnostics(Logger(), plan.diagnostics)
    assert len(messages) == 1
    assert "private information" not in messages[0]
    assert "event=unknown status=invalid position=5" in messages[0]
