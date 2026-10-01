from datetime import datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from core.day_partner import DayPartner
from core.google_calendar import CalendarReadOutcome, GoogleCalendarManager
from core.reminder_manager import ReminderManager
from skills.personal.google_calendar.skill import GoogleCalendarSkill


def calendar():
    mgr = GoogleCalendarManager.__new__(GoogleCalendarManager)
    mgr.config = type("Config", (), {"get": lambda self, key, default=None: "test-user" if key == "user_profiles.primary_user_id" else default})()
    mgr._jarvis_calendar_id = None
    mgr._authenticated = True
    mgr.creds = Mock(expired=False)
    mgr._include_primary = True
    mgr._timezone = "Europe/Berlin"
    mgr._ensure_valid = Mock(return_value=True)
    mgr.service = Mock()
    mgr.logger = Mock()
    return mgr


@pytest.mark.parametrize("date,period,start,end", [
    ("2026-03-29T12:00:00", "today", "2026-03-29T00:00:00+01:00", "2026-03-30T00:00:00+02:00"),
    ("2026-10-25T12:00:00", "today", "2026-10-25T00:00:00+02:00", "2026-10-26T00:00:00+01:00"),
    ("2026-09-30T23:59:00", "tomorrow", "2026-10-01T00:00:00+02:00", "2026-10-02T00:00:00+02:00"),
    ("2026-10-25T12:00:00", "week", "2026-10-19T00:00:00+02:00", "2026-10-26T00:00:00+01:00"),
])
def test_calendar_ranges_use_exclusive_local_midnight_and_dst(date, period, start, end):
    mgr = calendar()
    mgr.service.events.return_value.list.return_value.execute.return_value = {"items": []}
    outcome = mgr.read_events(period, datetime.fromisoformat(date))
    assert outcome.available and outcome.events == []
    args = mgr.service.events.return_value.list.call_args.kwargs
    assert args["timeMin"] == start and args["timeMax"] == end


def test_pages_offset_conversion_all_day_and_cancellation():
    mgr = calendar()
    event = {"summary": "synthetic", "start": {"dateTime": "2026-10-01T08:00:00Z"},
             "end": {"dateTime": "2026-10-01T09:00:00Z"}}
    mgr.service.events.return_value.list.return_value.execute.side_effect = [
        {"items": [event], "nextPageToken": "page"},
        {"items": [{"summary": "day", "start": {"date": "2026-10-01"},
                    "end": {"date": "2026-10-02"}}, dict(event, status="cancelled")]},
    ]
    result = mgr.read_events("tomorrow", datetime(2026, 9, 30))
    assert len(result.events) == 2
    timed = next(event for event in result.events if not event["all_day"])
    assert timed["start_time"] == datetime(2026, 10, 1, 10)
    assert timed["end_time"] == datetime(2026, 10, 1, 11)
    assert any(event["all_day"] for event in result.events)
    assert mgr.service.events.return_value.list.call_args.kwargs["pageToken"] == "page"


def test_read_failure_not_empty_success_and_no_private_error_log():
    mgr = calendar()
    mgr.service.events.return_value.list.return_value.execute.side_effect = RuntimeError("PRIVATE_TITLE_TOKEN")
    assert mgr.read_events().status == "unavailable"
    assert "PRIVATE_TITLE_TOKEN" not in str(mgr.logger.method_calls)
    mgr._authenticated = False
    mgr.service.reset_mock()
    assert mgr.read_events().status == "auth_blocked"
    mgr.service.events.assert_not_called()


def test_unknown_profile_fail_closed_before_all_reads():
    rm, cm = Mock(), Mock()
    cm.can_access_user.return_value = True
    assert "Nutzerprofil" in DayPartner(rm, cm).get_overview()
    assert not rm.mock_calls and not cm.mock_calls


def test_calendar_blocked_keeps_scoped_reminders_and_avoids_false_free_plan():
    rm, cm = Mock(), Mock()
    cm.can_access_user.return_value = True
    cm.read_events.return_value = CalendarReadOutcome("auth_blocked")
    rm._query_rundown_reminders.return_value = [{"title": "synthetic", "reminder_time": "2026-10-01 17:00:00"}]
    text = DayPartner(rm, cm).get_overview("today", True, "test-user", datetime(2026, 10, 1, 9))
    assert "nicht verfügbar" in text and "synthetic" in text and "nicht sicher planen" in text
    assert rm._query_rundown_reminders.call_args.kwargs["created_by"] == "test-user"
    rm.add_reminder.assert_not_called()
    cm.create_event.assert_not_called()


def test_plan_overlap_buffer_and_no_mutations():
    rm, cm = Mock(), Mock()
    cm.can_access_user.return_value = True
    rm._query_rundown_reminders.return_value = []
    cm.read_events.return_value = CalendarReadOutcome("success", [
        {"title": "one", "start_time": datetime(2026, 10, 1, 10), "end_time": datetime(2026, 10, 1, 11)},
        {"title": "two", "start_time": datetime(2026, 10, 1, 10, 30), "end_time": datetime(2026, 10, 1, 12)},
    ])
    text = DayPartner(rm, cm).get_overview("today", True, "test-user", datetime(2026, 10, 1, 9))
    assert "Überschneidung" in text and "12:15 bis 20:00" in text
    assert "kein Termin" in text
    assert cm.read_events.call_count == 1 and len(rm.mock_calls) == 1


@pytest.mark.parametrize("phrase,hour", [("morgen früh", 8), ("morgen um 17 Uhr", 17), ("um 17 Uhr", 17)])
def test_german_reminder_times(phrase, hour):
    parsed = ReminderManager.parse_natural_time(phrase)
    assert parsed is not None and parsed.hour == hour


def test_invalid_reminder_hour_returns_no_time():
    assert ReminderManager.parse_natural_time("morgen um 29 Uhr") is None


def test_auth_never_starts_interactive_oauth_when_missing_token(tmp_path):
    mgr = calendar()
    mgr._token_path = str(tmp_path / "missing.json")
    mgr._credentials_path = str(tmp_path / "credentials.json")
    with pytest.raises(PermissionError):
        mgr._authenticate()
    mgr.service.events.assert_not_called()


def calendar_skill():
    skill = GoogleCalendarSkill.__new__(GoogleCalendarSkill)
    skill.conversation = Mock(current_user="test-user")
    skill._manager_ref = Mock(is_connected=True, _jarvis_calendar_id="dedicated-test")
    skill._pending_confirmation = None
    skill._manager_ref.can_access_user.return_value = True
    return skill


@pytest.mark.parametrize("action", ["create", "update", "delete"])
def test_calendar_writes_wait_for_explicit_confirmation(action):
    skill = calendar_skill()
    payload = {"title": "synthetic", "start_time": datetime(2026, 10, 1, 17), "event_id": "exact-test-id"}
    assert "bestätigen" in skill.request_write(action, payload)
    assert not [call for call in skill.manager.method_calls if call[0] != "can_access_user"]
    assert "Ja oder Nein" in skill.confirm_action({"original_text": "javascript"})
    assert not [call for call in skill.manager.method_calls if call[0] != "can_access_user"]
    assert "gespeichert" in skill.confirm_action({"original_text": "Ja bitte"})
    assert len([call for call in skill.manager.method_calls if call[0] != "can_access_user"]) == 1
    assert "wartet" in skill.confirm_action({"original_text": "Ja"})
    assert len([call for call in skill.manager.method_calls if call[0] != "can_access_user"]) == 1


@pytest.mark.parametrize("condition", ["denial", "expiry", "requester", "calendar", "disconnected"])
def test_calendar_write_invalid_confirmation_context_never_writes(condition):
    skill = calendar_skill()
    skill.request_write("delete", {"title": "synthetic", "event_id": "exact-test-id"})
    if condition == "expiry":
        a, d, _ = skill._pending_confirmation
        skill._pending_confirmation = a, d, 0
    elif condition == "requester":
        skill.conversation.current_user = "other-user"
    elif condition == "calendar":
        skill.manager._jarvis_calendar_id = "changed-id"
    elif condition == "disconnected":
        skill.manager.is_connected = False
    skill.confirm_action({"original_text": "ja nein" if condition == "denial" else "Ja"})
    assert not [call for call in skill.manager.method_calls if call[0] != "can_access_user"]
    assert skill._pending_confirmation is None


def test_existing_calendar_never_created_implicitly():
    mgr = calendar()
    mgr._calendar_name = "JARVIS"
    mgr._jarvis_calendar_id = None
    mgr.service.calendarList.return_value.list.return_value.execute.return_value = {"items": []}
    mgr._ensure_jarvis_calendar()
    mgr.service.calendars.assert_not_called()


def test_calendar_selection_requires_exact_title_not_substring():
    mgr = calendar()
    mgr._jarvis_calendar_id = "test-calendar"
    mgr.service.events.return_value.list.return_value.execute.return_value = {"items": [
        {"id": "one", "summary": "synthetic longer", "start": {"date": "2026-10-01"}},
        {"id": "two", "summary": "synthetic", "start": {"date": "2026-10-01"}},
    ]}
    result = mgr.find_dedicated_events("synthetic")
    assert [event["google_event_id"] for event in result] == ["two"]


def test_real_local_reminder_crud_never_mirrors_remote_and_gate_denies_writes(tmp_path, monkeypatch):
    import threading
    from core.privacy_gate import PrivacyGate, PrivacyMode, PrivacyViolation
    import core.reminder_manager as module
    mgr = ReminderManager.__new__(ReminderManager)
    mgr.db_path = tmp_path / "reminders.sqlite"
    mgr._db_lock = threading.Lock()
    mgr.logger = Mock()
    mgr._calendar_manager = Mock()
    mgr.default_snooze = 15
    mgr._init_db()
    gate = PrivacyGate()
    monkeypatch.setattr(module, "get_privacy_gate", lambda: gate)
    rid = mgr.add_reminder("PRIVATE_SYNTHETIC", datetime(2026, 10, 1, 17), created_by="test-user")
    assert mgr.get_reminder(rid)["title"] == "PRIVATE_SYNTHETIC"
    assert mgr.snooze_reminder(rid)
    assert mgr.acknowledge_reminder(rid)
    assert mgr.cancel_reminder(rid)
    assert not mgr._calendar_manager.mock_calls
    assert "PRIVATE_SYNTHETIC" not in str(mgr.logger.mock_calls)
    gate.enter(PrivacyMode.PRIVACY)
    for operation in [lambda: mgr.add_reminder("blocked", datetime(2026, 10, 1)),
                      lambda: mgr.cancel_reminder(rid), lambda: mgr.snooze_reminder(rid)]:
        with pytest.raises(PrivacyViolation):
            operation()
    assert mgr.get_reminder(rid)["status"] == "cancelled"


def test_calendar_remote_gate_blocks_read_before_service(monkeypatch):
    import core.google_calendar as module
    from core.privacy_gate import PrivacyGate, PrivacyMode
    mgr = calendar()
    mgr.creds = Mock()
    gate = PrivacyGate()
    gate.enter(PrivacyMode.PRIVACY_LOCK)
    monkeypatch.setattr(module, "get_privacy_gate", lambda: gate)
    del mgr._ensure_valid
    assert mgr.read_events().status == "privacy_blocked"
    assert not mgr.service.mock_calls


@pytest.mark.parametrize("user", [None, "", "__guest__", "guest", "unknown", "anonymous"])
def test_day_partner_guest_and_unknown_are_rejected_before_private_reads(user):
    rm, cm = Mock(), Mock()
    cm.can_access_user.return_value = True
    assert "Nutzerprofil" in DayPartner(rm, cm).get_overview(created_by=user)
    assert not rm.mock_calls and not cm.mock_calls


def test_day_partner_normalizes_mixed_reminder_offsets():
    rm, cm = Mock(), Mock()
    cm.can_access_user.return_value = True
    rm._query_rundown_reminders.return_value = [
        {"title": "aware", "reminder_time": "2026-10-01T08:00:00+00:00"},
        {"title": "naive", "reminder_time": "2026-10-01 09:00:00"},
    ]
    cm.read_events.return_value = CalendarReadOutcome("success", [])
    text = DayPartner(rm, cm).get_overview(created_by="test-user", now=datetime(2026, 10, 1, 8))
    assert text.index("naive") < text.index("aware")
    assert "10:00 Uhr: aware" in text


@pytest.mark.parametrize("user", [None, "__guest__", "unknown"])
def test_reminder_tool_missing_or_guest_profile_never_reads_or_writes(monkeypatch, user):
    import core.tools.manage_reminders as tool
    mgr = Mock()
    monkeypatch.setattr(tool, "_reminder_manager", mgr)
    monkeypatch.setattr(tool, "_current_user_fn", (lambda: user) if user else None)
    for action in ["list", "add", "cancel", "cancel_all", "acknowledge", "snooze"]:
        assert "Nutzerprofil" in tool.handler({"action": action})
    assert not mgr.mock_calls


def test_reminder_tool_ack_and_snooze_scope_current_profile(monkeypatch):
    import core.tools.manage_reminders as tool
    mgr = Mock()
    mgr.acknowledge_last.return_value = {"title": "synthetic"}
    mgr.snooze_last.return_value = {"title": "synthetic"}
    monkeypatch.setattr(tool, "_reminder_manager", mgr)
    monkeypatch.setattr(tool, "_current_user_fn", lambda: "test-user")
    tool.handler({"action": "acknowledge"})
    tool.handler({"action": "snooze", "snooze_minutes": 10})
    mgr.acknowledge_last.assert_called_once_with(created_by="test-user")
    mgr.snooze_last.assert_called_once_with(10, created_by="test-user")


def test_german_skill_creates_correct_title_and_explicit_time():
    from skills.personal.reminders.skill import ReminderSkill
    skill = ReminderSkill.__new__(ReminderSkill)
    assert skill._parse_reminder_command("Erinnere mich heute um 17 Uhr an den Einkauf") == {
        "time_text": "heute um 17 Uhr", "title": "den Einkauf"}
    assert skill._parse_reminder_command("Erinnere mich morgen früh an den Anruf") == {
        "time_text": "morgen früh", "title": "den Anruf"}


def test_calendar_privacy_change_after_preview_prevents_write(monkeypatch):
    import skills.personal.google_calendar.skill as module
    from core.privacy_gate import PrivacyGate, PrivacyMode
    gate = PrivacyGate()
    monkeypatch.setattr(module, "get_privacy_gate", lambda: gate)
    skill = calendar_skill()
    skill.request_write("delete", {"title": "synthetic", "event_id": "exact-test-id"})
    gate.enter(PrivacyMode.PRIVACY_LOCK)
    assert "gesperrt" in skill.confirm_action({"original_text": "Ja"})
    assert not [call for call in skill.manager.method_calls if call[0] != "can_access_user"]


def test_reminder_only_overview_does_not_touch_calendar():
    rm, cm = Mock(), Mock()
    cm.can_access_user.return_value = True
    rm.list_range.return_value = []
    text = DayPartner(rm, cm).get_overview(created_by="test-user", sources="reminders")
    assert "Kalender" not in text
    assert not cm.read_events.mock_calls


def test_actual_calendar_crud_adapter_requests_and_duration_preservation():
    mgr = calendar()
    mgr._jarvis_calendar_id = "dedicated-test"
    mgr.creds = Mock()
    mgr.creds.has_scopes.return_value = True
    resource = mgr.service.events.return_value
    resource.insert.return_value.execute.return_value = {"id": "synthetic-id"}
    assert mgr.create_event("synthetic", datetime(2026, 10, 1, 17)) == "synthetic-id"
    assert resource.insert.call_args.kwargs["calendarId"] == "dedicated-test"
    event = {"start": {"dateTime": "2026-10-01T10:00:00+02:00"},
             "end": {"dateTime": "2026-10-01T11:30:00+02:00"}}
    resource.get.return_value.execute.return_value = event
    assert mgr.update_event("synthetic-id", start_time=datetime(2026, 10, 2, 9))
    assert resource.update.call_args.kwargs["body"]["end"]["dateTime"] == "2026-10-02T10:30:00"
    assert mgr.delete_event("synthetic-id")
    assert resource.delete.call_args.kwargs == {"calendarId": "dedicated-test", "eventId": "synthetic-id"}


def test_readonly_token_cannot_write_calendar():
    mgr = calendar()
    mgr._jarvis_calendar_id = "dedicated-test"
    mgr.creds = Mock()
    mgr.creds.has_scopes.return_value = False
    assert mgr.create_event("synthetic", datetime(2026, 10, 1)) is None
    assert not mgr.update_event("synthetic-id", title="synthetic")
    assert not mgr.delete_event("synthetic-id")
    assert not mgr.service.mock_calls


def test_google_calendar_metadata_adopts_actual_primary_and_dedicated_timezone():
    mgr = calendar()
    mgr._calendar_name = "JARVIS"
    mgr._jarvis_calendar_id = None
    mgr.service.calendarList.return_value.list.return_value.execute.return_value = {"items": [
        {"id": "dedicated-test", "summary": "JARVIS", "timeZone": "Europe/Berlin"},
        {"id": "primary-test", "primary": True, "timeZone": "America/New_York"},
    ]}
    mgr._ensure_jarvis_calendar()
    assert mgr._primary_timezone == "America/New_York" and mgr.timezone_verified
    assert mgr._timezone == "Europe/Berlin" and mgr._jarvis_calendar_id == "dedicated-test"
    mgr.service.events.return_value.list.return_value.execute.return_value = {"items": []}
    mgr.read_events("today", datetime(2026, 10, 1, 12))
    assert mgr.service.events.return_value.list.call_args.kwargs["timeMin"].endswith("-04:00")
    mgr.service.calendars.assert_not_called()


def test_calendar_mandatory_german_command_creates_confirmation_only():
    skill = calendar_skill()
    skill._last_user_text = "Trag morgen um 10 Uhr einen Testtermin ein"
    assert "bestätigen" in skill.create_calendar_event()
    action, detail, _ = skill._pending_confirmation
    assert action == "create" and detail["title"] == "Testtermin" and detail["start_time"].hour == 10
    assert not [call for call in skill.manager.method_calls if call[0] != "can_access_user"]


@pytest.fixture
def local_reminders(tmp_path):
    import threading
    mgr = ReminderManager.__new__(ReminderManager)
    mgr.db_path = tmp_path / "scoped.sqlite"
    mgr._db_lock = threading.Lock()
    mgr._calendar_manager = None
    mgr.config = type("Config", (), {"get": lambda self, key, default=None: "test-user" if key == "user_profiles.primary_user_id" else default})()
    mgr.logger = Mock()
    mgr.default_snooze = 15
    mgr._last_announced_id = None
    mgr._init_db()
    return mgr


def test_actual_two_user_day_partner_sql_is_scoped_and_includes_synced_copy(local_reminders):
    mgr = local_reminders
    owner_id = mgr.add_reminder("OWNER", datetime(2026, 10, 1, 17), created_by="test-user")
    mgr.add_reminder("SECONDARY", datetime(2026, 10, 1, 18), created_by="secondary")
    synced = mgr.add_reminder("SYNCED", datetime(2026, 9, 30, 17), created_by="test-user")
    mgr._update_status(synced, "pending", google_event_id="remote:10", event_time="2026-10-01 19:00:00")
    text = DayPartner(mgr).get_overview(created_by="test-user", now=datetime(2026, 10, 1, 9))
    assert "OWNER" in text and "SECONDARY" not in text and "19:00 Uhr: SYNCED" in text
    rows = mgr._query_rundown_reminders("2026-10-01 00:00:00", "2026-10-01 23:59:59", created_by="secondary")
    assert [row["title"] for row in rows] == ["SECONDARY"]


def test_real_manager_skill_and_tool_snooze_are_profile_scoped(local_reminders, monkeypatch):
    from types import SimpleNamespace
    from skills.personal.reminders.skill import ReminderSkill
    import core.tools.manage_reminders as tool
    mgr = local_reminders
    owner = mgr.add_reminder("OWNER", datetime(2026, 10, 1, 17), priority=1, created_by="test-user")
    other = mgr.add_reminder("OTHER", datetime(2026, 10, 1, 17), priority=1, created_by="secondary")
    for rid in [owner, other]:
        mgr._update_status(rid, "fired")
    mgr._last_announced_id = other
    assert mgr.snooze_last(10, created_by="test-user") is None
    assert mgr.get_reminder(other)["status"] == "fired"
    mgr._last_announced_id = None
    skill = ReminderSkill.__new__(ReminderSkill)
    skill.conversation = SimpleNamespace(current_user="test-user")
    skill._manager_ref = mgr
    skill._last_user_text = "Verschiebe um 10 Minuten"
    skill.respond = lambda text: text
    assert "Verschoben" in skill.snooze_current()
    assert mgr.get_reminder(owner)["status"] == "snoozed"
    assert mgr.get_reminder(other)["status"] == "fired"
    monkeypatch.setattr(tool, "_reminder_manager", mgr)
    monkeypatch.setattr(tool, "_current_user_fn", lambda: "secondary")
    tool.handler({"action": "snooze", "snooze_minutes": 5})
    assert mgr.get_reminder(other)["status"] == "snoozed"


def test_owner_policy_uses_existing_primary_profile_config():
    mgr = calendar()
    assert mgr.can_access_user("test-user")
    for user in ["secondary", "__guest__", "unknown", None]:
        assert not mgr.can_access_user(user)
    mgr.config = type("Config", (), {"get": lambda self, key, default=None: default})()
    assert mgr.can_access_user("primary_user")
    assert not mgr.can_access_user("test-user")


def test_nonowner_calendar_read_and_write_denied_but_own_reminders_work(local_reminders):
    mgr = calendar()
    mgr.read_events = Mock(side_effect=AssertionError("owner calendar may not be read"))
    local_reminders.add_reminder("SECONDARY", datetime(2026, 10, 1, 18), created_by="secondary")
    text = DayPartner(local_reminders, mgr).get_overview(created_by="secondary", now=datetime(2026, 10, 1, 9))
    assert "nicht freigegeben" in text and "SECONDARY" in text
    mgr.read_events.assert_not_called()
    skill = calendar_skill()
    skill._manager_ref = mgr
    skill.conversation.current_user = "secondary"
    assert "nicht freigegeben" in skill.request_write("delete", {"event_id": "test-id"})
    assert not mgr.service.mock_calls


def test_calendar_primary_and_dedicated_events_read_and_only_actual_copies_dedup(local_reminders):
    mgr = calendar()
    mgr._jarvis_calendar_id = "dedicated-test"
    event = {"id": "remote", "summary": "REMOTE", "start": {"dateTime": "2026-10-01T10:00:00+02:00"}}
    mgr.service.events.return_value.list.return_value.execute.side_effect = [
        {"items": []}, {"items": [event]},
    ]
    local_reminders.add_reminder("LOCAL", datetime(2026, 10, 1, 15), created_by="test-user")
    copy = local_reminders.add_reminder("REMOTE", datetime(2026, 10, 1, 9), created_by="test-user")
    local_reminders._update_status(copy, "pending", google_event_id="remote:60", event_time="2026-10-01 10:00:00")
    missing = local_reminders.add_reminder("UNREPRESENTED", datetime(2026, 10, 1, 16), created_by="test-user")
    local_reminders._update_status(missing, "pending", google_event_id="missing:10", event_time="2026-10-01 17:00:00")
    text = DayPartner(local_reminders, mgr).get_overview(created_by="test-user", now=datetime(2026, 10, 1, 8))
    assert text.count("REMOTE") == 2  # One displayed entry, once as the next action.
    assert "LOCAL" in text and "17:00 Uhr: UNREPRESENTED" in text
    assert [call.kwargs["calendarId"] for call in mgr.service.events.return_value.list.call_args_list] == ["primary", "dedicated-test"]
    mgr.service.reset_mock()
    reminder_text = DayPartner(local_reminders, mgr).get_overview(created_by="test-user", now=datetime(2026, 10, 1, 8), sources="reminders")
    assert "09:00 Uhr: REMOTE" in reminder_text and "16:00 Uhr: UNREPRESENTED" in reminder_text
    assert not mgr.service.mock_calls


def test_real_owner_policy_change_after_preview_and_secondary_find_deny():
    mgr = calendar()
    mgr._jarvis_calendar_id = "dedicated-test"
    skill = calendar_skill()
    skill._manager_ref = mgr
    assert "bestätigen" in skill.request_write("delete", {"title": "synthetic", "event_id": "exact-id"})
    mgr.config = type("Config", (), {"get": lambda self, key, default=None: "other-owner"})()
    assert "gesperrt" in skill.confirm_action({"original_text": "Ja"})
    assert not mgr.service.mock_calls
    mgr.find_dedicated_events = Mock(side_effect=AssertionError("must not find owner calendar"))
    skill._last_user_text = "Lösche den Termin synthetic aus dem Kalender"
    skill.delete_calendar_event()
    mgr.find_dedicated_events.assert_not_called()


def test_new_google_sync_copy_belongs_to_configured_primary_profile(local_reminders):
    mgr = local_reminders
    mgr.config = type("Config", (), {"get": lambda self, key, default=None: "configured-owner"})()
    rid = mgr._on_google_new_event("synthetic", datetime.now() + timedelta(days=2),
                                   3, "synthetic-google-id", 10)
    assert mgr.get_reminder(rid)["created_by"] == "configured-owner"


def test_nonowner_legacy_google_copy_hidden_but_local_reminder_retained(local_reminders):
    rm, cm = local_reminders, calendar()
    copied = rm.add_reminder("OWNER_CALENDAR_PRIVATE", datetime(2026, 10, 1, 17), created_by="secondary")
    rm._update_status(copied, "pending", google_event_id="legacy-id", event_time="2026-10-01 17:00:00")
    rm.add_reminder("OWN_LOCAL", datetime(2026, 10, 1, 18), created_by="secondary")
    cm.read_events = Mock(side_effect=AssertionError("no remote read"))
    for sources in ["all", "reminders"]:
        text = DayPartner(rm, cm).get_overview(created_by="secondary", now=datetime(2026, 10, 1, 8), sources=sources)
        assert "OWNER_CALENDAR_PRIVATE" not in text and "OWN_LOCAL" in text
    cm.read_events.assert_not_called()


def test_actual_reminder_skill_today_cannot_bypass_calendar_copy_owner_policy(local_reminders, monkeypatch):
    from types import SimpleNamespace
    from skills.personal.reminders.skill import ReminderSkill
    import core.day_partner as module
    class Today(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 1, 8, tzinfo=tz)
    monkeypatch.setattr(module, "datetime", Today)
    mgr = local_reminders
    copied = mgr.add_reminder("OWNER_PRIVATE", datetime(2026, 10, 1, 17), created_by="secondary")
    mgr._update_status(copied, "pending", google_event_id="legacy-copy-id")
    mgr.add_reminder("OWN_LOCAL", datetime(2026, 10, 1, 18), created_by="secondary")
    skill = ReminderSkill.__new__(ReminderSkill)
    skill.conversation = SimpleNamespace(current_user="secondary")
    skill._manager_ref = mgr
    skill._last_user_text = "Welche Erinnerungen habe ich heute?"
    skill.respond = lambda text: text
    text = skill.list_reminders()
    assert "OWN_LOCAL" in text and "OWNER_PRIVATE" not in text


def test_actual_german_reminder_skill_read_and_scheduler_reach_callbacks(local_reminders, monkeypatch):
    """Synthetic callback acceptance; this makes no claim about microphone/playback."""
    import sys
    import threading
    from types import SimpleNamespace, ModuleType
    import core.reminder_manager as reminder_module
    import core.day_partner as day_module
    import skills.personal.reminders.skill as skill_module
    import core.user_profile as profile_module

    class Clock(datetime):
        current = datetime(2026, 10, 1, 9)

        @classmethod
        def now(cls, tz=None):
            value = cls.current
            return cls(value.year, value.month, value.day, value.hour, value.minute, tzinfo=tz)

    for module in [reminder_module, day_module, skill_module]:
        monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(profile_module, "ProfileManager", lambda config: SimpleNamespace(
        get_honorific_for=lambda user: "sir", get_formal_address_for=lambda user: "Herr Test"))
    desktop = ModuleType("core.desktop_manager")
    desktop.get_desktop_manager = lambda: None
    monkeypatch.setitem(sys.modules, "core.desktop_manager", desktop)

    mgr = local_reminders
    skill = skill_module.ReminderSkill.__new__(skill_module.ReminderSkill)
    skill.conversation = SimpleNamespace(current_user="test-user")
    skill._manager_ref = mgr
    skill.respond = lambda text: text
    for command in ["Erinnere mich heute um 17 Uhr an X", "Erinnere mich morgen früh an Y"]:
        skill._last_user_text = command
        assert "Erinnerung gesetzt" in skill.set_reminder()
    rows = mgr.list_reminders(created_by="test-user")
    assert [(row["title"], row["reminder_time"]) for row in rows] == [
        ("x", "2026-10-01 17:00:00"), ("y", "2026-10-02 08:00:00")]
    skill._last_user_text = "Welche Erinnerungen habe ich heute?"
    read = skill.list_reminders()
    assert "17:00 Uhr: x" in read and ": y" not in read

    callbacks, spoken = [], []
    mgr._stop_event = threading.Event()
    mgr._pause_listener_callback = lambda: callbacks.append("pause")
    def resume():
        callbacks.append("resume")
        mgr._stop_event.set()
    mgr._resume_listener_callback = resume
    mgr._ack_window_callback = None
    mgr.tts = SimpleNamespace(speak=lambda text: spoken.append(text) or True)
    mgr._play_priority_tone = Mock()
    mgr._sync_mobility_demand = Mock()
    mgr._announcing_missed = False
    mgr.rundown_enabled = False
    mgr.poll_interval = 30
    mgr._running = True
    Clock.current = datetime(2026, 10, 1, 17)
    mgr._poll_loop()
    assert callbacks == ["pause", "resume"]
    assert len(spoken) == 1 and "Erinnerung" in spoken[0] and "X" in spoken[0]
    assert mgr.get_reminder(rows[0]["id"])["status"] == "confirmed"
    assert mgr.get_reminder(rows[0]["id"])["fire_count"] == 1
    assert mgr.get_reminder(rows[1]["id"])["status"] == "pending"


@pytest.fixture
def trigger_transport(local_reminders, monkeypatch):
    import sys
    import threading
    from types import SimpleNamespace, ModuleType
    import core.reminder_manager as module
    import core.user_profile as profiles
    class Clock(datetime):
        current = datetime(2026, 10, 1, 17)
        @classmethod
        def now(cls, tz=None):
            return cls.current if tz is None else cls.current.replace(tzinfo=tz)
    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(profiles, "ProfileManager", lambda config: SimpleNamespace(
        get_honorific_for=lambda user: "sir", get_formal_address_for=lambda user: "Herr Test"))
    desktop = ModuleType("core.desktop_manager")
    desktop.get_desktop_manager = lambda: None
    monkeypatch.setitem(sys.modules, "core.desktop_manager", desktop)
    mgr = local_reminders
    mgr._stop_event = threading.Event()
    mgr.poll_interval = 30
    mgr.nag_max_count = 3
    mgr._pause_listener_callback = Mock()
    mgr._resume_listener_callback = Mock()
    mgr._ack_window_callback = Mock()
    mgr._play_priority_tone = Mock()
    mgr.tts = SimpleNamespace(speak=Mock())
    return mgr, Clock


@pytest.mark.parametrize("failure", [False, RuntimeError("PRIVATE_TRANSPORT_DETAIL")])
def test_real_reminder_tts_failure_waits_then_retry_success(trigger_transport, failure):
    mgr, clock = trigger_transport
    mgr.tts.speak.side_effect = [failure, True]
    rid = mgr.add_reminder("PRIVATE_SYNTHETIC", clock.current, created_by="test-user")
    due = mgr._check_due_reminders()
    assert [row["id"] for row in due] == [rid]
    mgr._fire_reminder(due[0])
    failed = mgr.get_reminder(rid)
    assert failed["status"] == "pending" and failed["fire_count"] == 1
    mgr._ack_window_callback.assert_not_called()
    assert mgr._last_announced_id is None
    assert mgr._check_due_reminders() == []
    clock.current += timedelta(seconds=29)
    assert mgr._check_due_reminders() == []
    clock.current += timedelta(seconds=1)
    retry = mgr._check_due_reminders()
    assert [row["id"] for row in retry] == [rid]
    mgr._fire_reminder(retry[0])
    delivered = mgr.get_reminder(rid)
    assert delivered["status"] == "confirmed" and delivered["fire_count"] == 2
    assert mgr._check_due_reminders() == []
    assert mgr.tts.speak.call_count == 2
    assert mgr._pause_listener_callback.call_count == mgr._resume_listener_callback.call_count == 2
    assert "PRIVATE_SYNTHETIC" not in str(mgr.logger.mock_calls)
    assert "PRIVATE_TRANSPORT_DETAIL" not in str(mgr.logger.mock_calls)


def test_failed_reminder_retry_cap_and_stop_event_prevent_more_attempts(trigger_transport):
    mgr, clock = trigger_transport
    mgr.tts.speak.return_value = False
    rid = mgr.add_reminder("synthetic", clock.current, created_by="test-user")
    for attempt in range(3):
        due = mgr._check_due_reminders()
        assert [row["id"] for row in due] == [rid]
        mgr._fire_reminder(due[0])
        clock.current += timedelta(seconds=30)
    assert mgr.get_reminder(rid)["status"] == "pending"
    assert mgr.get_reminder(rid)["fire_count"] == 3
    assert mgr._check_due_reminders() == []
    assert mgr.tts.speak.call_count == 3
    later = mgr.add_reminder("later", clock.current, created_by="test-user")
    mgr._stop_event.set()
    assert mgr._check_due_reminders() == []
    assert mgr.get_reminder(later)["fire_count"] == 0


def test_explicit_snooze_starts_fresh_bounded_delivery_attempts(trigger_transport):
    mgr, clock = trigger_transport
    rid = mgr.add_reminder("synthetic", clock.current, priority=1, created_by="test-user")
    mgr._update_status(rid, "fired", fire_count=3, last_fired_at=clock.current.strftime("%Y-%m-%d %H:%M:%S"))
    mgr._last_announced_id = rid
    assert mgr.snooze_last(1, created_by="test-user")["id"] == rid
    clock.current += timedelta(minutes=1)
    mgr._check_snoozed()
    row = mgr.get_reminder(rid)
    assert row["status"] == "pending" and row["fire_count"] == 0 and row["last_fired_at"] is None
    assert [item["id"] for item in mgr._check_due_reminders()] == [rid]
