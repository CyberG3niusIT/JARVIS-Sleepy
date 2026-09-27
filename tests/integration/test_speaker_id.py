"""Speaker embedding extraction with real Torch/SciPy and a local fake encoder.

These tests never download an inference model, record audio, or persist a
runtime voiceprint. Enrollment and identification policy is covered in unit
tests, where reference vectors live only in pytest temporary directories.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from core.speaker_id import EMBEDDING_DIM, SpeakerIdentifier


class _Config:
    def get(self, key, default=None):
        return default


class _Encoder:
    def __init__(self):
        self.waveforms = []

    def encode_batch(self, waveform):
        import torch

        self.waveforms.append(waveform.detach().cpu().numpy().copy())
        result = torch.zeros((1, 1, EMBEDDING_DIM), dtype=torch.float32)
        result[0, 0, 0] = 1.0
        return result


@pytest.fixture
def speaker():
    sid = SpeakerIdentifier(_Config(), SimpleNamespace())
    encoder = _Encoder()
    sid._encoder = encoder
    return sid, encoder


def _sine(sample_rate, duration_seconds=1.0):
    t = np.arange(int(sample_rate * duration_seconds), dtype=np.float64) / sample_rate
    return np.sin(2 * np.pi * 440 * t).astype(np.float32)


def test_extract_embedding_resamples_48khz_to_16khz(speaker):
    sid, encoder = speaker

    embedding = sid.extract_embedding(_sine(48000), sample_rate=48000)

    assert embedding.shape == (EMBEDDING_DIM,)
    assert embedding.dtype == np.float32
    assert encoder.waveforms[0].shape == (1, 16000)


def test_extract_embedding_normalizes_volume_and_converts_float64(speaker):
    sid, encoder = speaker
    audio = (_sine(16000) * 0.02).astype(np.float64)

    sid.extract_embedding(audio)

    waveform = encoder.waveforms[0]
    assert waveform.dtype == np.float32
    assert float(np.sqrt(np.mean(waveform ** 2))) == pytest.approx(0.1, abs=1e-3)


def test_extract_embedding_rejects_audio_shorter_than_100ms(speaker):
    sid, encoder = speaker

    embedding = sid.extract_embedding(np.ones(1599, dtype=np.float32))

    np.testing.assert_array_equal(embedding, np.zeros(EMBEDDING_DIM, dtype=np.float32))
    assert encoder.waveforms == []
