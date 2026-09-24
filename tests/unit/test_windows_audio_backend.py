"""Regression tests for JARVIS' native Windows audio backend.

No real audio device, PowerShell process, Chatterbox server or Piper binary is
used. These tests only protect dispatch, WAV wrapping and cleanup semantics.
"""

import io
import os
import sys
import threading
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

from core.tts import TextToSpeech


class _NullLogger:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


class _Result:
    stdout = r"C:\Users\Alex\AppData\Local\Temp\JARVIS\test.wav\n"


class _Stderr:
    def __init__(self, data=b""):
        self.data = data

    def read(self):
        return self.data


class _Proc:
    def __init__(self, rc=0, stderr=b""):
        self.returncode = None
        self._rc = rc
        self.stderr = _Stderr(stderr)
        self.pid = 1234
        self.killed = False

    def wait(self, timeout=None):
        self.returncode = self._rc
        return self._rc

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


def _bare_tts(tmp_path):
    tts = TextToSpeech.__new__(TextToSpeech)
    tts.logger = _NullLogger()
    tts.windows_temp_dir = tmp_path
    tts.sample_rate = 24000
    tts.output_backend = "windows"
    tts._active_procs = []
    tts._active_procs_lock = threading.Lock()
    return tts


def test_play_wav_windows_success_and_cleanup(tmp_path, monkeypatch):
    tts = _bare_tts(tmp_path)
    popen_calls = []

    monkeypatch.setattr("core.tts.subprocess.run", lambda *a, **k: _Result())

    def fake_popen(args, **kwargs):
        popen_calls.append(args)
        return _Proc(rc=0)

    monkeypatch.setattr("core.tts.subprocess.Popen", fake_popen)

    assert tts._play_wav_windows(b"RIFF-test-data") is True
    assert popen_calls
    assert popen_calls[0][0] == "powershell.exe"
    assert list(tmp_path.glob("jarvis-*.wav")) == []


def test_play_wav_windows_failure_still_cleans_temp_file(tmp_path, monkeypatch):
    tts = _bare_tts(tmp_path)
    monkeypatch.setattr("core.tts.subprocess.run", lambda *a, **k: _Result())
    monkeypatch.setattr(
        "core.tts.subprocess.Popen",
        lambda *a, **k: _Proc(rc=1, stderr=b"simulated PowerShell failure"),
    )

    assert tts._play_wav_windows(b"RIFF-test-data") is False
    assert list(tmp_path.glob("jarvis-*.wav")) == []


def test_play_pcm_windows_wraps_expected_wave_format(tmp_path):
    tts = _bare_tts(tmp_path)
    captured = {}

    def capture(wav_bytes):
        captured["wav"] = wav_bytes
        return True

    tts._play_wav_windows = capture
    pcm = b"\x01\x00" * 100

    assert tts._play_pcm_windows(pcm, 24000) is True

    with wave.open(io.BytesIO(captured["wav"]), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.readframes(wf.getnframes()) == pcm


def test_speak_routes_chatterbox_to_windows_backend(tmp_path):
    tts = _bare_tts(tmp_path)
    tts._tts_lock = threading.Lock()
    tts._spoke = False
    tts._tts_cache = {}
    tts.normalization_enabled = False
    tts.normalizer = None
    tts.engine = "chatterbox"

    calls = []
    tts._speak_chatterbox_windows = lambda text, timeout_override=None: calls.append(text) or True
    tts._speak_chatterbox = lambda *a, **k: (_ for _ in ()).throw(AssertionError("WSL backend used"))
    tts._fallback_to_piper = lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected fallback"))

    assert tts.speak("Hallo Alex.") is True
    assert calls == ["Hallo Alex."]


def test_piper_fallback_uses_windows_pcm_path(tmp_path):
    tts = _bare_tts(tmp_path)
    tts._piper_ready = True
    tts._piper_sample_rate = 22050
    tts._piper_generate_pcm = lambda text: (b"\x02\x00" * 10, 22050)

    seen = {}

    def play(pcm, sr):
        seen["pcm"] = pcm
        seen["sr"] = sr
        return True

    tts._play_pcm_windows = play

    assert tts._fallback_to_piper("Fallback") is True
    assert seen["sr"] == 22050
    assert seen["pcm"]


def test_directed_speak_skips_whole_text_cache_and_plays_once(tmp_path):
    tts = _bare_tts(tmp_path)
    tts._tts_lock = threading.Lock()
    tts._spoke = False
    tts._tts_cache = {
        "Hallo Welt": b"stale cached speech",
        "Hallo[voice:pause=short]Welt": b"stale directed speech",
    }
    tts.normalization_enabled = False
    tts.normalizer = None
    tts.engine = "chatterbox"
    seen = []
    tts._chatterbox_generate_pcm = lambda text: (seen.append(text) or b"\x01\x00", 24000)
    tts._piper_generate_pcm = lambda text: (_ for _ in ()).throw(AssertionError("unexpected fallback"))
    played = []
    tts._play_pcm_windows = lambda pcm, rate: played.append((pcm, rate)) or True

    assert tts.speak("Hallo[voice:pause=short]Welt") is True
    assert seen == ["Hallo", "Welt"]
    assert len(played) == 1
    assert len(played[0][0]) == 4 + 24000 * 200 // 1000 * 2


def test_directed_unsupported_tag_is_not_spoken_or_cached(tmp_path):
    tts = _bare_tts(tmp_path)
    tts._tts_lock = threading.Lock()
    tts._spoke = False
    tts._tts_cache = {"Hallo Welt": b"stale cached speech"}
    tts.normalization_enabled = False
    tts.normalizer = None
    tts.engine = "chatterbox"
    seen = []
    tts._speak_chatterbox_windows = lambda text, timeout_override=None: seen.append(text) or True
    assert tts.speak("Hallo[voice:cough]Welt") is True
    assert seen == ["Hallo Welt"]


def test_literal_voice_over_text_keeps_cache_key(tmp_path):
    tts = _bare_tts(tmp_path)
    tts._tts_lock = threading.Lock()
    tts._spoke = False
    tts._tts_cache = {"Ein [voice-over] Test.": b"\x00\x00" * 10}
    tts.normalization_enabled = False
    tts.normalizer = None
    tts.engine = "chatterbox"
    tts._play_pcm_windows = lambda pcm, rate: True
    tts._speak_chatterbox_windows = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("cache was bypassed")
    )
    assert tts.speak("Ein [voice-over] Test.") is True
