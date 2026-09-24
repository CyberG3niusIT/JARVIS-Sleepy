"""Demand leases and configured trips. All HTTP responses are synthetic."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
import requests

from core.mobility_planner import MobilityPlanner
from core.mobility_contract import MobilityErrorReason, MobilityStatus
from core.privacy_gate import get_privacy_gate, reset_privacy_gate_singleton_for_tests, PrivacyMode


class Config(dict):
    def get(self, path, default=None):
        result = self
        for part in path.split("."):
            if not isinstance(result, dict) or part not in result:
                return default
            result = result[part]
        return result


@pytest.fixture
def planner(tmp_path, monkeypatch):
    reset_privacy_gate_singleton_for_tests()
    result = MobilityPlanner(Config({"mobility": {"base_url": "http://127.0.0.1:8088",
        "db_path": str(tmp_path / "mobility.db")}}))
    response = Mock(status_code=200)
    result._session.post = Mock(return_value=response)
    result._session.delete = Mock(return_value=response)
    monkeypatch.setattr("core.mobility_planner.time.time", lambda: datetime(2027, 3, 1, 5, tzinfo=timezone.utc).timestamp())
    yield result
    result._session.close()
    reset_privacy_gate_singleton_for_tests()


def configure(planner, person="*", departure="07:10", purpose="school_arrival", **kwargs):
    planner.set_stop_preference("test-origin", "efa-origin", pinned=True, recurring=True, verified=True)
    planner.set_stop_preference("test-school", "efa-school", verified=True)
    planner.set_journey_rule(person, purpose, departure, "test-origin", "test-school", line="TEST-LINE", **kwargs)


def event(purpose="school_arrival", person="test-person"):
    return {"person_id": person, "purpose": purpose, "event_time": datetime(2027, 3, 1, 8)}


def payload(departure="07:10", arrival="07:40", line="TEST-LINE"):
    return {"journeys": [{"legs": [{
        "origin": {"planned": "2027-03-01T" + departure + ":00+01:00", "name": "Synthetic origin"},
        "destination": {"planned": "2027-03-01T" + arrival + ":00+01:00", "name": "Synthetic destination"},
        "transport": {"line": line, "product_class": 5},
    }]}]}


def route_mock(journey, state="realtime", canceled=None, departures=None):
    static = {"departures": [{"planned_departure": "2027-03-01T07:10:00+01:00",
        "route_short_name": "TEST-LINE", "trip_schedule_relationship": canceled}],
        "realtime_state": {"state": state, "age_seconds": 3}}
    if departures is not None:
        static["departures"] = departures
    return Mock(side_effect=lambda path, params: static if path.endswith("/departures") else journey)


def test_demand_exact_berlin_windows(planner):
    configure(planner)
    assert planner.sync_demand([event()]) == {"status": "registered", "windows": 1}
    body = planner._session.post.call_args.kwargs["json"]
    epoch = lambda hour, minute: datetime(2027, 3, 1, hour, minute, tzinfo=timezone.utc).timestamp()
    assert body == {"client_id": "jarvis-school", "windows": [
        {"start": epoch(5, 30), "active_start": epoch(6, 0), "end": epoch(7, 30)}]}
    assert planner._session.post.call_args.kwargs["allow_redirects"] is False


def test_demand_registration_does_not_fetch_routes(planner, monkeypatch):
    configure(planner)
    monkeypatch.setattr(planner, "_get", Mock(side_effect=AssertionError("No query in scheduler")))
    planner.sync_demand([event()])


def test_demand_refresh_at_most_every_300_seconds(planner, monkeypatch):
    configure(planner)
    planner.sync_demand([event()])
    initial = planner._demand_last_attempt
    monkeypatch.setattr("core.mobility_planner.time.time", lambda: initial + 299)
    assert planner.sync_demand([event()])["throttled"] is True
    assert planner._session.post.call_count == 1
    monkeypatch.setattr("core.mobility_planner.time.time", lambda: initial + 300)
    planner.sync_demand([event()])
    assert planner._session.post.call_count == 2


def test_empty_events_release_only_once(planner):
    configure(planner)
    planner.sync_demand([event()])
    assert planner.sync_demand([])["status"] == "idle"
    planner.sync_demand([])
    assert planner._session.delete.call_count == 1


def test_privacy_lock_revokes_once_and_never_registers(planner):
    configure(planner)
    get_privacy_gate().enter(PrivacyMode.PRIVACY_LOCK)
    planner.sync_demand([event()])
    planner.sync_demand([event()])
    assert planner._session.delete.call_count == 1
    planner._session.post.assert_not_called()
    assert planner.plan_school_event(event()).error_reason == MobilityErrorReason.PRIVACY_BLOCKED


def test_no_demand_without_verified_mapping(planner):
    configure(planner)
    planner.set_stop_preference("test-origin", "efa-origin", verified=False)
    planner.sync_demand([event()])
    planner._session.post.assert_not_called()
    assert planner.plan_school_event(event()).error_reason == MobilityErrorReason.NOT_CONFIGURED


def test_no_demand_for_unknown_or_invalid_events(planner):
    planner.sync_demand([event(), {"event_time": "bad"}, None])
    planner._session.post.assert_not_called()


def test_demand_deduplicates_windows(planner):
    configure(planner)
    assert planner.sync_demand([event(), event(person="second-test-person")])["windows"] == 1


def test_person_and_weekday_override_generic_rules(planner):
    configure(planner)
    configure(planner, person="test-person", departure="07:20")
    configure(planner, person="test-person", departure="07:30", weekday=0)
    rules = planner.get_journey_rules("test-person", "school_arrival", 0)
    assert [rule["departure"] for rule in rules] == ["07:30"]
    assert planner.get_journey_rules("test-person", "school_arrival", 1)[0]["departure"] == "07:20"
    assert planner.get_journey_rules("other-test-person", "school_arrival", 0)[0]["departure"] == "07:10"


@pytest.mark.parametrize("changes", [{"departure": "7:10"}, {"departure": "25:00"}, {"weekday": 7}, {"weekday": True}])
def test_invalid_rule_rejected(planner, changes):
    arguments = dict(person_id="test", purpose="school_arrival", departure="07:10", origin="a", destination="b")
    arguments.update(changes)
    with pytest.raises(ValueError):
        planner.set_journey_rule(**arguments)


def test_preferred_departure_only_no_unconfigured_alternative(planner, monkeypatch):
    configure(planner)
    query = route_mock(payload(departure="07:13"))
    monkeypatch.setattr(planner, "_get", query)
    result = planner.plan_school_event(event())
    assert result.error_reason == MobilityErrorReason.NO_JOURNEY_FOUND
    assert query.call_args.args[1]["at"] == "2027-03-01T07:10:00"


def test_configured_route_is_schedule_only_without_estimates(planner, monkeypatch):
    configure(planner)
    monkeypatch.setattr(planner, "_get", route_mock(payload()))
    result = planner.plan_school_event(event())
    assert result.status == MobilityStatus.SCHEDULE_ONLY
    assert result.leave_at == datetime(2027, 3, 1, 7, 10)
    assert result.legs[0].canceled is None


def test_configured_wrong_line_rejected(planner, monkeypatch):
    configure(planner)
    monkeypatch.setattr(planner, "_get", route_mock(payload(line="UNCONFIGURED")))
    assert planner.plan_school_event(event()).error_reason == MobilityErrorReason.NO_JOURNEY_FOUND


def test_afternoon_is_arrival_deadline(planner, monkeypatch):
    configure(planner, purpose="school_arrival_afternoon")
    monkeypatch.setattr(planner, "_get", route_mock(payload(arrival="08:01")))
    assert planner.plan_school_event(event(purpose="school_arrival_afternoon")).error_reason == MobilityErrorReason.NO_JOURNEY_FOUND


def test_return_cannot_leave_before_school_end(planner, monkeypatch):
    configure(planner, purpose="school_return", departure="07:10")
    query = route_mock(payload(departure="07:10", arrival="07:40"))
    monkeypatch.setattr(planner, "_get", query)
    result = planner.plan_school_event(event(purpose="school_return"))
    assert result.error_reason == MobilityErrorReason.NO_JOURNEY_FOUND
    assert query.call_count == 2


@pytest.mark.parametrize("url", ["https://example.com", "http://192.168.1.1:8088", "http://127.0.0.1:8088?secret=x"])
def test_non_loopback_urls_are_unconfigured(tmp_path, url):
    planner = MobilityPlanner(Config({"mobility": {"base_url": url, "db_path": str(tmp_path / "m.db")}}))
    assert planner.base_url == ""


def test_failed_demand_registration_is_throttled_and_not_success(planner):
    configure(planner)
    planner._session.post.side_effect = requests.exceptions.ConnectionError("offline")
    assert planner.sync_demand([event()])["status"] == "unavailable"
    planner.sync_demand([event()])
    assert planner._session.post.call_count == 1


def test_actual_fresh_cancellation_is_reported_without_efa_query(planner, monkeypatch):
    configure(planner)
    query = route_mock(payload(), canceled="CANCELED")
    monkeypatch.setattr(planner, "_get", query)
    assert planner.plan_school_event(event()).error_reason == MobilityErrorReason.JOURNEY_CANCELED
    assert query.call_count == 1


def test_missed_preferred_departure_uses_configured_fallback(planner, monkeypatch):
    configure(planner, departure="07:10", priority=50)
    planner.set_journey_rule("*", "school_arrival", "07:40", "test-origin", "test-school",
                             line="TEST-LINE", priority=100)

    from datetime import datetime as RealDateTime

    class FrozenDateTime(RealDateTime):
        @classmethod
        def now(cls, tz=None):
            return cls(2027, 3, 1, 7, 30, tzinfo=tz)

    monkeypatch.setattr("core.mobility_planner.datetime", FrozenDateTime)
    test_event = {"person_id": "test-person", "purpose": "school_arrival",
                  "event_time": FrozenDateTime(2027, 3, 1, 8)}
    departure_row = {"planned_departure": "2027-03-01T07:40:00+01:00",
                     "route_short_name": "TEST-LINE", "trip_schedule_relationship": None}
    query = route_mock(payload(departure="07:40", arrival="08:00"), departures=[departure_row])
    monkeypatch.setattr(planner, "_get", query)

    result = planner.plan_school_event(test_event)

    assert result.leave_at == FrozenDateTime(2027, 3, 1, 7, 40)
    assert query.call_count == 3
    assert query.call_args.args[1]["at"] == "2027-03-01T07:40:00"


def test_stale_cancellation_not_claimed_current(planner, monkeypatch):
    configure(planner)
    monkeypatch.setattr(planner, "_get", route_mock(payload(), state="stale", canceled="CANCELED"))
    result = planner.plan_school_event(event())
    assert result.status == MobilityStatus.DEGRADED
    assert result.error_reason == MobilityErrorReason.REALTIME_STALE
    assert result.legs[0].canceled is None


def test_unconfirmed_scheduled_departure_never_queries_efa(planner, monkeypatch):
    configure(planner)
    query = route_mock(payload(), departures=[])
    monkeypatch.setattr(planner, "_get", query)
    assert planner.plan_school_event(event()).error_reason == MobilityErrorReason.NO_JOURNEY_FOUND
    assert query.call_count == 1


def test_ambiguous_scheduled_departures_need_direction(planner, monkeypatch):
    configure(planner)
    rows = [{"planned_departure": "2027-03-01T07:10:00+01:00", "route_short_name": "TEST-LINE"}] * 2
    monkeypatch.setattr(planner, "_get", route_mock(payload(), departures=rows))
    assert planner.plan_school_event(event()).error_reason == MobilityErrorReason.LOCATION_AMBIGUOUS


def test_failed_release_retries_no_more_than_every_300_seconds(planner):
    planner._session.delete.side_effect = requests.exceptions.ConnectionError("offline")
    assert planner.sync_demand([])["status"] == "release_failed"
    planner.sync_demand([])
    assert planner._session.delete.call_count == 1
