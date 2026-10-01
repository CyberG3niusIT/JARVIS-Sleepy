"""Real idle poll threads wake on stop without executing another cycle."""
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.news_manager import NewsManager
from core.weather_poller import WeatherPoller
from core.reminder_manager import ReminderManager
from core.presence_detector import PresenceDetector


class ObservedEvent:
    def __init__(self, skip_first_wait=False):
        self.event = threading.Event()
        self.waiting = threading.Event()
        self.skip_first_wait = skip_first_wait
    def clear(self):
        self.event.clear()
        self.waiting.clear()
    def set(self):
        self.event.set()
    def is_set(self):
        return self.event.is_set()
    def wait(self, timeout):
        if self.skip_first_wait:
            self.skip_first_wait = False
            return False
        self.waiting.set()
        return self.event.wait(timeout)


def manager(kind, interval=False, skipped=False):
    instance = kind.__new__(kind)
    instance.logger = Mock()
    instance.config = SimpleNamespace(get=lambda key, default=None: default)
    instance._running = False
    instance._poll_thread = None
    instance._stop_event = ObservedEvent(interval and kind is not ReminderManager)
    instance.poll_interval = 60
    instance._poll_once = Mock()
    instance.feeds = ["controlled"]
    instance.owm_key = "test-placeholder"
    instance.poll_interval_alert = 60
    instance._db = SimpleNamespace(get_active_alerts=lambda: [])
    instance._maybe_populate_sun_times = Mock()
    instance._face_app = None
    instance._interval = 60
    instance._should_skip = Mock(return_value=skipped)
    instance._publish_npu_sensor = Mock()
    instance._check_presence = Mock()
    instance._announcing_missed = skipped
    instance._startup_timer = None
    instance.startup_delay = 60
    instance.scan_missed_reminders = Mock(return_value=[])
    instance.announce_missed_reminders = Mock()
    instance._sync_mobility_demand = Mock()
    instance._check_due_reminders = Mock(return_value=[])
    instance.get_pending_acks = Mock(return_value=[])
    instance._check_snoozed = Mock()
    instance.rundown_enabled = False
    return instance


@pytest.mark.parametrize("kind", [NewsManager, WeatherPoller, ReminderManager, PresenceDetector])
@pytest.mark.parametrize("interval", [False, True])
def test_idle_stop_wakes_real_poll_thread(kind, interval):
    instance = manager(kind, interval)
    instance.start()
    assert instance._stop_event.waiting.wait(1), "poll thread did not enter idle wait"
    before = (instance._poll_once.call_count, instance._check_presence.call_count,
              instance._check_due_reminders.call_count)
    started = time.monotonic()
    instance.stop()
    assert time.monotonic() - started < 1
    assert not instance._poll_thread.is_alive()
    assert before == (instance._poll_once.call_count, instance._check_presence.call_count,
                      instance._check_due_reminders.call_count)
    instance.announce_missed_reminders.assert_not_called()


@pytest.mark.parametrize("kind", [ReminderManager, PresenceDetector])
def test_skipped_cycle_wait_is_interruptible(kind):
    instance = manager(kind, interval=True, skipped=True)
    instance.start()
    assert instance._stop_event.waiting.wait(1)
    instance.stop()
    assert not instance._poll_thread.is_alive()
    instance._check_presence.assert_not_called()
    instance._check_due_reminders.assert_not_called()


def test_missed_reminder_timer_is_daemon_cancelled_and_guarded():
    instance = manager(ReminderManager)
    instance.scan_missed_reminders.return_value = ["controlled reminder"]
    instance.start()
    timer = instance._startup_timer
    assert timer.daemon
    assert instance._stop_event.waiting.wait(1)
    instance.stop()
    timer.join(timeout=1)
    assert not timer.is_alive()
    instance._announce_missed_after_startup()
    instance.announce_missed_reminders.assert_not_called()


@pytest.mark.parametrize("kind", [NewsManager, WeatherPoller, ReminderManager, PresenceDetector])
def test_start_after_stop_clears_stop_event(kind):
    instance = manager(kind)
    instance._stop_event.set()
    instance.start()
    assert instance._stop_event.waiting.wait(1)
    assert not instance._stop_event.is_set()
    instance.stop()
    assert not instance._poll_thread.is_alive()
