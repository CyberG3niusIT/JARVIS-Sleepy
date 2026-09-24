"""Single primary speaker identification using synthetic unit-test vectors only."""

from types import SimpleNamespace

import numpy as np
import pytest

from core.speaker_id import EMBEDDING_DIM, SpeakerIdentifier
from core.user_profile import ProfileManager


class _Config:
    def __init__(self, storage_path):
        self.values = {
            "system.storage_path": str(storage_path),
            "user_profiles.primary_user_id": "primary_user",
            "user_profiles.primary_user_name": "Alex",
            "user_profiles.similarity_threshold": 0.80,
            "user_profiles.auto_enroll": False,
        }

    def get(self, key, default=None):
        return self.values.get(key, default)


def _vector(index):
    vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vector[index] = 1.0
    return vector


@pytest.fixture
def speaker(tmp_path, monkeypatch):
    config = _Config(tmp_path)
    profiles = ProfileManager(config)
    profiles.create_profile("primary_user", "Alex", honorific="sir", role="admin")
    sid = SpeakerIdentifier(config, profiles)
    vectors = {1: _vector(0), 2: _vector(1), 3: _vector(2), 4: _vector(3)}

    # No microphone or inference model is loaded in these unit tests.
    monkeypatch.setattr(
        sid,
        "extract_embedding",
        lambda audio, sample_rate=16000: vectors[int(audio[0])],
    )
    return SimpleNamespace(sid=sid, profiles=profiles, vectors=vectors)


def _audio(marker):
    return np.full(3200, marker, dtype=np.float32)


def _enroll(speaker):
    return speaker.sid.enroll_from_multiple(
        "primary_user", [(_audio(index), 16000) for index in (1, 2, 3)]
    )


def test_primary_profile_seeding_is_idempotent_and_has_no_voiceprint(tmp_path):
    profiles = ProfileManager(_Config(tmp_path))

    first = profiles.ensure_primary_profile()
    second = profiles.ensure_primary_profile()

    assert first["id"] == second["id"] == "primary_user"
    assert first["name"] == "Alex"
    assert first["honorific"] == "sir"
    assert first["embedding_path"] is None
    assert [profile["id"] for profile in profiles.get_all()] == ["primary_user"]


def test_enrollment_retains_multiple_distinct_primary_references(speaker):
    assert _enroll(speaker)
    path = speaker.profiles.get_profile("primary_user")["embedding_path"]
    references = np.load(path)
    assert references.shape == (3, EMBEDDING_DIM)
    np.testing.assert_allclose(np.linalg.norm(references, axis=1), 1.0)
    assert not np.allclose(references[0], references[1])


def test_each_enrolled_voice_variation_matches_primary_user(speaker):
    assert _enroll(speaker)
    speaker.sid.load_embeddings()
    for marker in (1, 2, 3):
        user_id, score = speaker.sid.identify(_audio(marker))
        assert user_id == "primary_user"
        assert score == pytest.approx(1.0)


def test_unrelated_voice_is_unknown_and_does_not_mutate_enrollment(speaker):
    assert _enroll(speaker)
    path = speaker.profiles.get_profile("primary_user")["embedding_path"]
    before = np.load(path).copy()

    user_id, score = speaker.sid.identify(_audio(4))

    assert user_id is None
    assert score < speaker.sid.similarity_threshold
    np.testing.assert_array_equal(np.load(path), before)
    assert len(speaker.profiles.get_all()) == 1


def test_no_reference_means_unknown_without_automatic_enrollment(speaker):
    assert speaker.sid.identify(_audio(1)) == (None, 0.0)
    assert speaker.profiles.get_profile("primary_user")["embedding_path"] is None
    assert list(speaker.profiles.embeddings_dir.iterdir()) == []


def test_other_profile_cannot_be_enrolled_or_loaded(speaker):
    speaker.profiles.create_profile("other", "Other", honorific="sir")
    assert not speaker.sid.enroll_from_multiple(
        "other", [(_audio(index), 16000) for index in (1, 2, 3)]
    )
    assert speaker.profiles.get_profile("other")["embedding_path"] is None

    stale_path = speaker.profiles.embeddings_dir / "other.npy"
    np.save(stale_path, speaker.vectors[4])
    speaker.profiles.update_profile("other", embedding_path=str(stale_path))
    speaker.sid.load_embeddings()
    assert speaker.sid.identify(_audio(4))[0] is None


def test_one_or_two_clips_do_not_count_as_multi_sample_enrollment(speaker):
    assert not speaker.sid.enroll_from_multiple(
        "primary_user", [(_audio(index), 16000) for index in (1, 2)]
    )
    assert speaker.profiles.get_profile("primary_user")["embedding_path"] is None


def test_single_clip_enrollment_cannot_authorize_primary(speaker):
    assert not speaker.sid.enroll("primary_user", _audio(1))
    assert speaker.profiles.get_profile("primary_user")["embedding_path"] is None
    assert speaker.sid.identify(_audio(1))[0] is None


def test_legacy_single_reference_requires_explicit_multi_sample_reenrollment(speaker):
    path = speaker.profiles.embeddings_dir / "primary_user.npy"
    np.save(path, speaker.vectors[1])
    speaker.profiles.update_profile("primary_user", embedding_path=str(path))

    speaker.sid.load_embeddings()

    assert speaker.sid.identify(_audio(1))[0] is None
    assert _enroll(speaker)
    assert speaker.sid.identify(_audio(1))[0] == "primary_user"
