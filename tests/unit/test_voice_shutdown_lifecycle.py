"""Real lifecycle methods with synthetic workers, no microphone or runtime."""
import ast
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[2]


def isolated_methods(path, class_name, method_names, namespace=None):
    """Compile unchanged method bodies without importing hardware initializers."""
    source = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    owner = next(node for node in source.body
                 if isinstance(node, ast.ClassDef) and node.name == class_name)
    methods = [node for node in owner.body
               if isinstance(node, ast.FunctionDef) and node.name in method_names]
    assert {node.name for node in methods} == set(method_names)
    module = ast.Module(body=methods, type_ignores=[])
    env = {"threading": threading, "time": time, **(namespace or {})}
    exec(compile(ast.fix_missing_locations(module), str(ROOT / path), "exec"), env)
    return type(class_name, (), {name: env[name] for name in method_names})


@pytest.mark.parametrize("exit_error", (None, KeyboardInterrupt(), RuntimeError("synthetic exit")))
def test_run_cancels_pending_startup_health_timer_before_cleanup(monkeypatch, exit_error):
    worker = Mock()
    watcher = Mock()
    module = ModuleType("core.privacy_control_watcher")
    module.PrivacyControlWatcher = Mock(return_value=watcher)
    monkeypatch.setitem(sys.modules, "core.privacy_control_watcher", module)
    runtime_class = isolated_methods("jarvis_continuous.py", "JarvisContinuous", {"run"},
                                     {"TTSWorker": Mock(return_value=worker),
                                      "get_honorific": lambda: ""})
    runtime = runtime_class()
    runtime.event_mode = True
    runtime.wake_word = "jarvis"
    runtime.logger = Mock()
    runtime.listener = Mock()
    runtime.listener.start_with_retry.return_value = True
    runtime.stt_worker = Mock()
    runtime.tts = Mock()
    runtime.tts._chatterbox_session = None
    runtime.event_queue = Mock()
    runtime.audio_queue = Mock()
    runtime.tts_queue = Mock()
    runtime.config = {"health_check.run_on_startup": True, "watchdog.enabled": False}
    runtime.coordinator = Mock()
    runtime.coordinator.run.side_effect = exit_error
    runtime._run_startup_health_check = Mock()
    for name in ("memory_manager", "context_window", "presence_detector", "mcp_bridge",
                 "news_manager", "weather_poller", "mail_poller", "calendar_manager", "reminder_manager"):
        setattr(runtime, name, None)
    runtime.coordinator.shutdown.side_effect = lambda: (
        pytest.fail("Startup timer not cancelled before coordinator cleanup")
        if not runtime._startup_health_timer.finished.is_set() else None)
    if isinstance(exit_error, RuntimeError):
        with pytest.raises(RuntimeError, match="synthetic exit"):
            runtime.run()
    else:
        runtime.run()
    timer = runtime._startup_health_timer
    assert isinstance(timer, threading.Timer)
    assert timer.daemon is True
    assert timer.finished.is_set()
    timer.join(timeout=0.5)
    assert not timer.is_alive()
    runtime._run_startup_health_check.assert_not_called()
    runtime.coordinator.shutdown.assert_called_once()
    watcher.stop.assert_called_once()
    runtime.listener.stop.assert_called_once()


class ObservedEvent:
    def __init__(self):
        self.event = threading.Event()
        self.waiting = threading.Event()

    def clear(self):
        self.event.clear()
        self.waiting.clear()

    def set(self):
        self.event.set()

    def wait(self, timeout):
        self.waiting.set()
        return self.event.wait(timeout)


def test_idle_device_monitor_stop_wakes_and_never_reconnects():
    listener_class = isolated_methods("core/continuous_listener.py", "ContinuousListener", {
        "start_device_monitor", "stop_device_monitor", "_device_monitor_loop",
    })
    listener = listener_class()
    listener.logger = Mock()
    listener._monitor_thread = None
    listener._monitor_interval = 30
    listener._monitor_stop = ObservedEvent()
    listener.stream = None
    listener.start = Mock(side_effect=AssertionError("Reconnect after shutdown"))
    # Also verify an instance can restart its monitor after a clean stop.
    for _ in range(2):
        listener.start_device_monitor()
        thread = listener._monitor_thread
        assert listener._monitor_stop.waiting.wait(timeout=1), "Monitor did not enter idle wait"
        started = time.monotonic()
        listener.stop_device_monitor()
        assert time.monotonic() - started < 0.5
        assert not thread.is_alive()
        assert listener._monitor_thread is None
        listener.start.assert_not_called()
