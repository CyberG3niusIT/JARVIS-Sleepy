"""Unit tests for session #8 agentic-audit finding #4: the privacy
control sentinel files used to live directly under `/tmp`
(`/tmp/.jarvis_privacy_enter` etc.) — a world-writable directory where
any local user on the same host could create a same-named file and
flip this process's privacy mode. core/privacy_control_watcher.py now
resolves a user-private runtime directory via _default_runtime_dir():
$XDG_RUNTIME_DIR/jarvis or /run/user/$UID/jarvis when available
(systemd-managed, mode 0700, per-user), else a self-created, validated
/tmp/jarvis-$UID fallback (created 0700, ownership checked, symlinks
refused).
"""

import os
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.privacy_control_watcher import _default_runtime_dir, PrivacyControlWatcher


class TestDefaultRuntimeDirPrefersXdgRuntimeDir:
    def test_uses_xdg_runtime_dir_when_set(self, tmp_path, monkeypatch):
        xdg = tmp_path / "xdg-runtime"
        xdg.mkdir(mode=0o700)
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg))

        result = _default_runtime_dir()

        assert result == str(xdg / "jarvis")
        assert os.path.isdir(result)
        assert stat.S_IMODE(os.stat(result).st_mode) == 0o700

    def test_falls_back_to_tmp_jarvis_uid_when_no_xdg_and_no_run_user(
        self, monkeypatch
    ):
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        _real_isdir = os.path.isdir
        monkeypatch.setattr(
            os.path, "isdir",
            lambda p: False if p.startswith("/run/user/") else _real_isdir(p),
        )

        result = _default_runtime_dir()

        assert result == f"/tmp/jarvis-{os.getuid()}"
        assert _real_isdir(result)
        assert stat.S_IMODE(os.stat(result).st_mode) == 0o700


class TestDefaultRuntimeDirRefusesUntrustedDirectory:
    def test_refuses_directory_owned_by_a_different_uid(self, tmp_path, monkeypatch):
        """A pre-existing directory this process doesn't own must never
        be trusted, even if it happens to be writable — simulated here
        by monkeypatching os.getuid() so the real (matching) uid looks
        foreign to the resolver."""
        xdg = tmp_path / "xdg-runtime"
        xdg.mkdir(mode=0o700)
        candidate = xdg / "jarvis"
        candidate.mkdir(mode=0o700)  # owned by the real test-runner uid
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg))

        real_getuid = os.getuid
        # Make the resolver believe it's a different user than the
        # directory's actual owner, so the ownership check must reject it.
        monkeypatch.setattr(os, "getuid", lambda: real_getuid() + 12345)

        result = _default_runtime_dir()

        # Falls through past the untrusted XDG candidate to the final
        # /tmp fallback (still using the *real* getuid() is impossible
        # here since getuid is patched — so it either lands on the
        # spoofed-uid tmp path it can create+own itself, or plain /tmp).
        assert result != str(candidate)

    def test_refuses_symlinked_directory(self, tmp_path, monkeypatch):
        xdg = tmp_path / "xdg-runtime"
        xdg.mkdir(mode=0o700)
        real_target = tmp_path / "elsewhere"
        real_target.mkdir(mode=0o700)
        symlink_path = xdg / "jarvis"
        os.symlink(real_target, symlink_path)
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg))

        result = _default_runtime_dir()

        assert result != str(symlink_path)


class TestSentinelPathsUnderRuntimeDir:
    def test_class_sentinel_paths_are_not_bare_tmp(self):
        """The old bug: sentinels lived directly at /tmp/.jarvis_privacy_*
        — this must no longer be the case for the class defaults."""
        assert PrivacyControlWatcher.ENTER_SENTINEL != "/tmp/.jarvis_privacy_enter"
        assert PrivacyControlWatcher.LOCK_SENTINEL != "/tmp/.jarvis_privacy_lock"
        assert PrivacyControlWatcher.EXIT_SENTINEL != "/tmp/.jarvis_privacy_exit"
        assert PrivacyControlWatcher.STATUS_FILE != "/tmp/.jarvis_privacy_status"

    def test_sentinel_paths_share_a_common_runtime_dir(self):
        dirs = {
            os.path.dirname(PrivacyControlWatcher.ENTER_SENTINEL),
            os.path.dirname(PrivacyControlWatcher.LOCK_SENTINEL),
            os.path.dirname(PrivacyControlWatcher.EXIT_SENTINEL),
            os.path.dirname(PrivacyControlWatcher.STATUS_FILE),
        }
        assert len(dirs) == 1
