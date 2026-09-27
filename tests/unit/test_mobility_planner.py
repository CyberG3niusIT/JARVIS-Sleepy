"""Unit tests for core/mobility_planner.py.

HTTP is mocked at the requests.Session level (no requests_mock dependency
available in this repo's requirements.txt) using the preview's expected
journeys payload. The VVS schema has not been independently verified here.
No live network
call is made in these tests (task brief section 19: mark NICHT GETESTET
if a live VVS API instance isn't available — it isn't, here).
"""

import os
import sys
from datetime import datetime, timedelta
from dataclasses import replace
from datetime import timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest
import requests

from core.mobility_planner import MobilityPlanner
from core.mobility_contract import MobilityRequest, MobilityStatus, MobilityErrorReason
from core.privacy_gate import get_privacy_gate, reset_privacy_gate_singleton_for_tests, PrivacyMode


class _FakeConfig(dict):
    def get(self, path, default=None):
        parts = path.split(".")
        d = self
        for p in parts:
            if isinstance(d, dict) and p in d:
                d = d[p]
            else:
                return default
        return d


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.exceptions.HTTPError(response=self)
            raise err


@pytest.fixture(autouse=True)
def _privacy_normal():
    reset_privacy_gate_singleton_for_tests()
    yield
    reset_privacy_gate_singleton_for_tests()


@pytest.fixture
def planner(tmp_path):
    cfg = _FakeConfig({
        "mobility": {
            "base_url": "http://127.0.0.1:8090",
            "db_path": str(tmp_path / "mobility.db"),
            "default_arrival_buffer_minutes": 5,
        }
    })
    return MobilityPlanner(cfg)


def _leg(mode_transit=True, dep_planned="2027-03-01T11:40:00+01:00", dep_est=None,
         arr_planned="2027-03-01T11:52:00+01:00", arr_est=None, delay_seconds=None):
    """Build a leg matching the preview adapter contract (not a live capture)."""
    transport = {"line": "168", "product_class": 5} if mode_transit else {"line": None, "product_class": None}
    return {
        "duration_seconds": 720,
        "distance_m": None,
        "origin": {"id": "de:08115:1234", "name": "Testhaltestelle Nord", "type": "stop",
                    "planned": dep_planned, "estimated": dep_est, "delay_seconds": None},
        "destination": {"id": "de:08115:5678", "name": "Testhaltestelle Süd", "type": "stop",
                          "planned": arr_planned, "estimated": arr_est, "delay_seconds": delay_seconds},
        "transport": transport,
        "infos": [],
    }


def _journeys_payload(legs, system_messages=None):
    return {
        "source": "efa",
        "arrive_by": True,
        "system_messages": system_messages or [],
        "journeys": [{"rating": 100, "interchanges": 0, "is_additional": False, "legs": legs, "fare": None, "days_of_service": None}],
    }


def _request():
    return MobilityRequest(
        person_id="test_person",
        purpose="test_purpose",
        destination_id="de:08115:5678",
        origin_id="de:08115:1234",
        arrive_by=datetime(2027, 3, 1, 12, 0, 0),
    )


class TestJourneyNormalization:
    def test_schedule_only_when_no_estimated_present(self, planner, monkeypatch):
        payload = _journeys_payload([_leg()])
        monkeypatch.setattr(planner, "_get", lambda path, params: payload)

        result = planner.plan_arrival(_request())

        assert result.status == MobilityStatus.SCHEDULE_ONLY
        assert result.ok
        # naive local time — see core/mobility_planner.py's _parse_iso
        assert result.leave_at == datetime(2027, 3, 1, 11, 40, 0)
        assert result.arrival_at == datetime(2027, 3, 1, 11, 52, 0)

    def test_school_event_without_trip_matched_estimate_is_schedule_only(self, planner, monkeypatch):
        planner.set_stop_preference("de:08115:1234", "5001234", verified=True)
        planner.set_stop_preference("de:08115:5678", "5005678", verified=True)
        planner.set_journey_rule(
            "test_person", "school_arrival", "11:40",
            "de:08115:1234", "de:08115:5678", line="168", weekday=0,
        )

        def _get(path, params):
            if path.endswith("/departures"):
                return {
                    "departures": [{
                        "planned_departure": "2027-03-01T11:40:00+01:00",
                        "estimated_departure": None,
                        "route_short_name": "168",
                    }],
                    "realtime_state": {"state": "realtime", "age_seconds": 5},
                }
            # The EFA payload has estimated fields, but they only repeat the
            # timetable and the matched VVS trip has no realtime estimate.
            return _journeys_payload([_leg(
                dep_est="2027-03-01T11:40:00+01:00",
                arr_est="2027-03-01T11:52:00+01:00",
            )])

        monkeypatch.setattr(planner, "_get", _get)
        result = planner.plan_school_event({
            "person_id": "test_person",
            "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 12, 0),
        })

        assert result.status == MobilityStatus.SCHEDULE_ONLY
        assert result.leave_at == datetime(2027, 3, 1, 11, 40)
        assert "keine Echtzeitprognose" in result.message

    def test_school_arrival_uses_fallback_when_realtime_delay_misses_deadline(self, planner, monkeypatch):
        planner.set_stop_preference("de:08115:1234", "5001234", verified=True)
        planner.set_stop_preference("de:08115:5678", "5005678", verified=True)
        planner.set_stop_preference("de:08115:9012", "5009012", verified=True)
        planner.set_journey_rule(
            "test_person", "school_arrival", "07:18",
            "de:08115:1234", "de:08115:5678", line="144", priority=50, weekday=0,
        )
        planner.set_journey_rule(
            "test_person", "school_arrival", "07:48",
            "de:08115:1234", "de:08115:9012", line="168", priority=100, weekday=0,
        )

        def _get(path, params):
            if path.endswith("/departures"):
                planned = params["at"] + "+01:00"
                return {
                    "departures": [{
                        "planned_departure": planned,
                        # Synthetic 50-minute delay exercises the real fallback path.
                        "estimated_departure": "2027-03-01T08:08:00+01:00" if params["at"].endswith("07:18:00") else None,
                        "route_short_name": "144" if params["at"].endswith("07:18:00") else "168",
                    }],
                    "realtime_state": {"state": "realtime", "age_seconds": 5},
                }
            if params["to"] == "5005678":
                # First bus is 50 minutes late and misses the school deadline.
                leg = _leg(
                    dep_est="2027-03-01T08:08:00+01:00",
                    arr_planned="2027-03-01T07:40:00+01:00",
                    arr_est="2027-03-01T08:20:00+01:00",
                )
                leg["transport"]["line"] = "144"
                return _journeys_payload([leg])
            leg = _leg(
                dep_planned="2027-03-01T07:48:00+01:00",
                dep_est="2027-03-01T07:48:00+01:00",
                arr_planned="2027-03-01T07:58:00+01:00",
                arr_est="2027-03-01T07:58:00+01:00",
            )
            leg["transport"]["line"] = "168"
            return _journeys_payload([leg])

        monkeypatch.setattr(planner, "_get", _get)
        result = planner.plan_school_event({
            "person_id": "test_person",
            "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 8, 0),
        })

        assert result.ok
        assert result.leave_at == datetime(2027, 3, 1, 7, 48)
        assert result.request.destination_id == "de:08115:9012"
        assert result.legs[0].line == "168"

    def test_realtime_when_all_legs_have_estimates(self, planner, monkeypatch):
        payload = _journeys_payload([_leg(
            dep_est="2027-03-01T11:41:00+01:00",
            arr_est="2027-03-01T11:54:00+01:00",
            delay_seconds=120,
        )])
        monkeypatch.setattr(planner, "_get", lambda path, params: payload)

        result = planner.plan_arrival(_request())

        assert result.status == MobilityStatus.REALTIME
        assert result.leave_at == datetime(2027, 3, 1, 11, 41, 0)
        assert result.delay_minutes == 2

    def test_degraded_when_only_some_legs_have_estimates(self, planner, monkeypatch):
        leg_with_rt = _leg(dep_est="2027-03-01T11:41:00+01:00", arr_est="2027-03-01T11:44:00+01:00")
        leg_without_rt = _leg(dep_planned="2027-03-01T11:46:00+01:00", arr_planned="2027-03-01T11:55:00+01:00")
        payload = _journeys_payload([leg_with_rt, leg_without_rt])
        monkeypatch.setattr(planner, "_get", lambda path, params: payload)

        result = planner.plan_arrival(_request())

        assert result.status == MobilityStatus.DEGRADED

    @pytest.mark.parametrize("estimates", [
        {"dep_est": "2027-03-01T11:41:00+01:00"},
        {"arr_est": "2027-03-01T11:54:00+01:00"},
    ])
    def test_single_estimated_endpoint_is_degraded(self, planner, monkeypatch, estimates):
        monkeypatch.setattr(planner, "_get", lambda path, params: _journeys_payload([_leg(**estimates)]))
        assert planner.plan_arrival(_request()).status == MobilityStatus.DEGRADED

    def test_walking_access_does_not_downgrade_complete_transit(self, planner, monkeypatch):
        walk = _leg(mode_transit=False, dep_planned="2027-03-01T11:30:00+01:00", arr_planned="2027-03-01T11:35:00+01:00")
        transit = _leg(dep_est="2027-03-01T11:41:00+01:00", arr_est="2027-03-01T11:54:00+01:00")
        monkeypatch.setattr(planner, "_get", lambda path, params: _journeys_payload([walk, transit]))
        result = planner.plan_arrival(_request())
        assert result.status == MobilityStatus.REALTIME
        assert all(leg.canceled is None for leg in result.legs)
        assert result.data_age_seconds is None

    def test_zero_product_class_is_transit(self, planner, monkeypatch):
        leg = _leg(dep_est="2027-03-01T11:41:00+01:00")
        leg["transport"] = {"line": None, "product_class": 0}
        monkeypatch.setattr(planner, "_get", lambda path, params: _journeys_payload([leg]))
        assert planner.plan_arrival(_request()).status == MobilityStatus.DEGRADED

    def test_delayed_arrival_after_deadline_is_rejected(self, planner, monkeypatch):
        leg = _leg(dep_est="2027-03-01T11:41:00+01:00", arr_est="2027-03-01T12:04:00+01:00")
        monkeypatch.setattr(planner, "_get", lambda path, params: _journeys_payload([leg]))
        assert planner.plan_arrival(_request()).error_reason == MobilityErrorReason.NO_JOURNEY_FOUND

    def test_selects_latest_feasible_departure(self, planner, monkeypatch):
        payload = _journeys_payload([_leg()])
        payload["journeys"].append({"legs": [_leg(dep_planned="2027-03-01T11:44:00+01:00")]})
        payload["journeys"].append({"legs": [_leg(dep_planned="2027-03-01T11:50:00+01:00", arr_planned="2027-03-01T12:01:00+01:00")]})
        monkeypatch.setattr(planner, "_get", lambda path, params: payload)
        assert planner.plan_arrival(_request()).leave_at == datetime(2027, 3, 1, 11, 44)

    @pytest.mark.parametrize("payload", [None, [], {}, {"journeys": "bad"}, {"journeys": [None]}, {"journeys": [{"legs": [None]}]}, {"journeys": [{"legs": [{"origin": []}]}]}])
    def test_malformed_response_is_unavailable(self, planner, monkeypatch, payload):
        monkeypatch.setattr(planner, "_get", lambda path, params: payload)
        assert planner.plan_arrival(_request()).error_reason == MobilityErrorReason.INVALID_RESPONSE

    @pytest.mark.parametrize("changes", [
        {"dep_planned": None}, {"arr_planned": "invalid"},
        {"arr_planned": "2027-03-01T11:00:00+01:00"},
    ])
    def test_invalid_leg_times_are_unavailable(self, planner, monkeypatch, changes):
        monkeypatch.setattr(planner, "_get", lambda path, params: _journeys_payload([_leg(**changes)]))
        assert not planner.plan_arrival(_request()).ok

    def test_walk_leg_detected_when_no_line_or_product_class(self, planner, monkeypatch):
        payload = _journeys_payload([_leg(mode_transit=False)])
        monkeypatch.setattr(planner, "_get", lambda path, params: payload)

        result = planner.plan_arrival(_request())

        assert result.legs[0].mode.value == "walk"

    def test_system_messages_surface_in_result_message(self, planner, monkeypatch):
        payload = _journeys_payload([_leg()], system_messages=[{"text": "Baustelle zwischen X und Y"}])
        monkeypatch.setattr(planner, "_get", lambda path, params: payload)

        result = planner.plan_arrival(_request())

        assert "Baustelle" in result.message


def _iso_local_minute(minute_of_day):
    hour, minute = divmod(minute_of_day, 60)
    return datetime(2027, 3, 1, hour, minute, tzinfo=timezone(timedelta(hours=1))).isoformat()


def _school_pair_connection(departure_minute, arrival_minute, *, delay=0, state="realtime",
                            canceled=False, present=True, departure_delay=None,
                            arrival_delay=None, estimated_arrival=True, line=None):
    dep_delay = delay if departure_delay is None else departure_delay
    arr_delay = delay if arrival_delay is None else arrival_delay
    scheduled_departure = _iso_local_minute(departure_minute)
    scheduled_arrival = _iso_local_minute(arrival_minute)
    return {
        "line": line or ("144" if departure_minute == 7 * 60 + 18 else "168"),
        "state": state,
        "present": present,
        "canceled": canceled,
        "scheduled_departure": scheduled_departure,
        "scheduled_arrival": scheduled_arrival,
        "estimated_departure": _iso_local_minute(departure_minute + dep_delay) if dep_delay is not None else None,
        "estimated_arrival": _iso_local_minute(arrival_minute + arr_delay) if arr_delay is not None and estimated_arrival else None,
    }


def _configure_school_pair(planner):
    planner.set_stop_preference("test-origin", "5003906", verified=True)
    planner.set_stop_preference("test-primary", "5004220", verified=True)
    planner.set_stop_preference("test-fallback", "5003908", verified=True)
    planner.set_journey_rule("test_person", "school_arrival", "07:18",
                             "test-origin", "test-primary", line="144", priority=50, weekday=0)
    planner.set_journey_rule("test_person", "school_arrival", "07:48",
                             "test-origin", "test-fallback", line="168", priority=100, weekday=0)


def _school_pair_api(connections):
    def get(path, params):
        scheduled_clock = params["at"].split("T", 1)[1][:5]
        connection = connections[scheduled_clock]
        if path.endswith("/departures"):
            departures = []
            if connection["present"]:
                departures.append({
                    "planned_departure": connection["scheduled_departure"],
                    "estimated_departure": connection["estimated_departure"],
                    "route_short_name": connection["line"],
                    "trip_schedule_relationship": "CANCELED" if connection["canceled"] else None,
                })
            return {"departures": departures, "realtime_state": {
                "state": connection["state"], "age_seconds": 4}}
        leg = _leg(
            dep_planned=connection["scheduled_departure"],
            dep_est=connection["estimated_departure"],
            arr_planned=connection["scheduled_arrival"],
            arr_est=connection["estimated_arrival"],
        )
        leg["transport"]["line"] = connection["line"]
        return _journeys_payload([leg])
    return get


def _freeze_planner_now(monkeypatch, hour, minute):
    from datetime import datetime as RealDateTime

    class FrozenDateTime(RealDateTime):
        @classmethod
        def now(cls, tz=None):
            value = cls(2027, 3, 1, hour, minute)
            return value.replace(tzinfo=tz) if tz else value

    monkeypatch.setattr("core.mobility_planner.datetime", FrozenDateTime)
    return FrozenDateTime


class TestSchoolConnectionSelection:
    @pytest.mark.parametrize(("primary_delay", "expected_line"), [
        (0, "144"), (5, "144"), (20, "144"),
        (50, "168"), (90, "168"), (180, "168"),
    ])
    def test_selects_by_feasible_predicted_arrival_without_delay_threshold(
        self, planner, monkeypatch, primary_delay, expected_line,
    ):
        _configure_school_pair(planner)
        connections = {
            "07:18": _school_pair_connection(438, 450, delay=primary_delay),
            "07:48": _school_pair_connection(468, 478),
        }
        monkeypatch.setattr(planner, "_get", _school_pair_api(connections))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 8, 0),
        })

        assert result.ok
        assert result.legs[0].line == expected_line

    def test_fallback_delay_can_make_primary_best_even_when_primary_departs_later(self, planner, monkeypatch):
        _configure_school_pair(planner)
        connections = {
            "07:18": _school_pair_connection(438, 450, departure_delay=37, arrival_delay=27),
            "07:48": _school_pair_connection(468, 478, delay=45),
        }
        monkeypatch.setattr(planner, "_get", _school_pair_api(connections))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 8, 0),
        })

        assert result.legs[0].line == "144"
        assert result.leave_at == datetime(2027, 3, 1, 7, 55)
        assert result.arrival_at == datetime(2027, 3, 1, 7, 57)

    def test_fallback_can_win_when_predicted_arrival_beats_feasible_primary(self, planner, monkeypatch):
        _configure_school_pair(planner)
        connections = {
            "07:18": _school_pair_connection(438, 450, delay=20),
            "07:48": _school_pair_connection(468, 478, arrival_delay=-9),
        }
        monkeypatch.setattr(planner, "_get", _school_pair_api(connections))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 8, 0),
        })

        assert result.legs[0].line == "168"
        assert result.arrival_at == datetime(2027, 3, 1, 7, 49)

    def test_no_suitable_route_when_all_delayed_arrivals_miss_deadline(self, planner, monkeypatch):
        _configure_school_pair(planner)
        connections = {
            "07:18": _school_pair_connection(438, 450, delay=50),
            "07:48": _school_pair_connection(468, 478, delay=5),
        }
        monkeypatch.setattr(planner, "_get", _school_pair_api(connections))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 8, 0),
        })

        assert result.status == MobilityStatus.UNAVAILABLE
        assert result.error_reason == MobilityErrorReason.NO_JOURNEY_FOUND

    @pytest.mark.parametrize(("primary_canceled", "fallback_canceled", "expected_line", "error"), [
        (True, False, "168", None),
        (False, True, "144", None),
        (True, True, None, MobilityErrorReason.JOURNEY_CANCELED),
    ])
    def test_canceled_connections_are_not_selected(self, planner, monkeypatch,
            primary_canceled, fallback_canceled, expected_line, error):
        _configure_school_pair(planner)
        connections = {
            "07:18": _school_pair_connection(438, 450, canceled=primary_canceled),
            "07:48": _school_pair_connection(468, 478, canceled=fallback_canceled),
        }
        monkeypatch.setattr(planner, "_get", _school_pair_api(connections))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 8, 0),
        })

        assert result.error_reason == error
        assert (result.legs[0].line if result.legs else None) == expected_line

    @pytest.mark.parametrize(("now", "primary_departure_delay", "fallback_departure_delay", "expected_line"), [
        ((7, 30), 2, 0, "168"),  # primary departed; it is no longer boardable
        ((7, 50), 37, 1, "144"),  # fallback departed; primary is still boardable
    ])
    def test_boardability_uses_trusted_predicted_departure_not_schedule_only(
        self, planner, monkeypatch, now, primary_departure_delay, fallback_departure_delay, expected_line,
    ):
        _configure_school_pair(planner)
        frozen = _freeze_planner_now(monkeypatch, *now)
        connections = {
            "07:18": _school_pair_connection(438, 450, departure_delay=primary_departure_delay,
                                               arrival_delay=primary_departure_delay),
            "07:48": _school_pair_connection(468, 478, departure_delay=fallback_departure_delay,
                                               arrival_delay=fallback_departure_delay),
        }
        monkeypatch.setattr(planner, "_get", _school_pair_api(connections))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": frozen(2027, 3, 1, 9, 0),
        })

        assert result.legs[0].line == expected_line

    def test_stale_realtime_estimates_are_ignored_for_selection_and_output(self, planner, monkeypatch):
        _configure_school_pair(planner)
        connections = {
            "07:18": _school_pair_connection(438, 450, delay=180, state="stale"),
            "07:48": _school_pair_connection(468, 478, state="stale"),
        }
        monkeypatch.setattr(planner, "_get", _school_pair_api(connections))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 8, 0),
        })

        assert result.legs[0].line == "144"
        assert result.status == MobilityStatus.DEGRADED
        assert result.error_reason == MobilityErrorReason.REALTIME_STALE
        assert result.leave_at == datetime(2027, 3, 1, 7, 18)
        assert result.arrival_at == datetime(2027, 3, 1, 7, 30)
        assert result.legs[0].realtime_departure_at is None
        assert result.legs[0].realtime_arrival_at is None
        assert result.delay_minutes is None

    def test_partial_realtime_is_not_used_to_replan(self, planner, monkeypatch):
        _configure_school_pair(planner)
        connections = {
            "07:18": _school_pair_connection(438, 450, delay=50, estimated_arrival=False),
            "07:48": _school_pair_connection(468, 478, state="unavailable"),
        }
        monkeypatch.setattr(planner, "_get", _school_pair_api(connections))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 8, 0),
        })

        assert result.legs[0].line == "144"
        assert result.status == MobilityStatus.DEGRADED
        assert result.leave_at == datetime(2027, 3, 1, 7, 18)
        assert result.arrival_at == datetime(2027, 3, 1, 7, 30)
        assert result.legs[0].realtime_departure_at is None
        assert result.legs[0].realtime_arrival_at is None

    def test_partial_estimate_on_any_transit_leg_downgrades_entire_school_route(self, planner, monkeypatch):
        _configure_school_pair(planner)
        connections = {
            "07:18": _school_pair_connection(438, 470, departure_delay=37, arrival_delay=37),
            "07:48": _school_pair_connection(468, 478, state="unavailable"),
        }
        fallback_api = _school_pair_api(connections)

        def get(path, params):
            if path.endswith("/departures") and params["at"].endswith("07:48:00"):
                return fallback_api(path, params)
            if path.endswith("/departures"):
                return {"departures": [{
                    "planned_departure": _iso_local_minute(438),
                    "estimated_departure": _iso_local_minute(475),
                    "route_short_name": "144",
                }], "realtime_state": {"state": "realtime", "age_seconds": 2}}
            first = _leg(dep_planned=_iso_local_minute(438), dep_est=_iso_local_minute(475),
                         arr_planned=_iso_local_minute(450), arr_est=_iso_local_minute(487))
            first["transport"]["line"] = "144"
            second = _leg(dep_planned=_iso_local_minute(450), arr_planned=_iso_local_minute(470),
                          arr_est=_iso_local_minute(490))
            second["transport"]["line"] = "144"
            return _journeys_payload([first, second])

        monkeypatch.setattr(planner, "_get", get)

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 8, 0),
        })

        assert result.legs[0].line == "144"
        assert result.status == MobilityStatus.DEGRADED
        assert result.leave_at == datetime(2027, 3, 1, 7, 18)
        assert result.arrival_at == datetime(2027, 3, 1, 7, 50)
        assert all(leg.realtime_departure_at is None for leg in result.legs)
        assert all(leg.realtime_arrival_at is None for leg in result.legs)

    def test_realtime_on_one_connection_can_be_compared_with_other_schedule(self, planner, monkeypatch):
        _configure_school_pair(planner)
        connections = {
            "07:18": _school_pair_connection(438, 450, delay=20),
            "07:48": _school_pair_connection(468, 478, delay=180, state="stale"),
        }
        monkeypatch.setattr(planner, "_get", _school_pair_api(connections))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 8, 0),
        })

        assert result.legs[0].line == "144"
        assert result.status == MobilityStatus.REALTIME

    def test_late_departure_can_still_win_on_earlier_predicted_arrival(self, planner, monkeypatch):
        _configure_school_pair(planner)
        connections = {
            "07:18": _school_pair_connection(438, 450, departure_delay=37, arrival_delay=27),
            "07:48": _school_pair_connection(468, 478),
        }
        monkeypatch.setattr(planner, "_get", _school_pair_api(connections))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": datetime(2027, 3, 1, 8, 0),
        })

        assert result.legs[0].line == "144"
        assert result.leave_at == datetime(2027, 3, 1, 7, 55)
        assert result.arrival_at == datetime(2027, 3, 1, 7, 57)

    def test_long_active_delay_has_no_maximum_delay_cutoff(self, planner, monkeypatch):
        _configure_school_pair(planner)
        frozen = _freeze_planner_now(monkeypatch, 10, 0)
        connections = {
            "07:18": _school_pair_connection(438, 450, departure_delay=180, arrival_delay=187),
            "07:48": _school_pair_connection(468, 478, departure_delay=172, arrival_delay=187),
        }
        monkeypatch.setattr(planner, "_get", _school_pair_api(connections))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival",
            "event_time": frozen(2027, 3, 1, 11, 0),
        })

        assert result.legs[0].line == "144"
        assert result.leave_at == frozen(2027, 3, 1, 10, 18)
        assert result.status == MobilityStatus.REALTIME

    def test_tuesday_1318_line_144_does_not_invent_an_168_alternative(self, planner, monkeypatch):
        planner.set_stop_preference("test-origin", "5003906", verified=True)
        planner.set_stop_preference("test-school", "5003908", verified=True)
        planner.set_journey_rule("test_person", "school_arrival_afternoon", "13:18",
                                 "test-origin", "test-school", line="144", weekday=1)
        connection = _school_pair_connection(13 * 60 + 18, 13 * 60 + 20, canceled=True, line="144")
        connection = {key: value.replace("2027-03-01", "2027-03-02") if isinstance(value, str) else value
                      for key, value in connection.items()}
        monkeypatch.setattr(planner, "_get", _school_pair_api({"13:18": connection}))

        result = planner.plan_school_event({
            "person_id": "test_person", "purpose": "school_arrival_afternoon",
            "event_time": datetime(2027, 3, 2, 14, 0),
        })

        assert result.error_reason == MobilityErrorReason.JOURNEY_CANCELED
        assert not result.legs


class TestErrorModes:
    def test_no_journey_found(self, planner, monkeypatch):
        monkeypatch.setattr(planner, "_get", lambda path, params: {"journeys": [], "system_messages": []})
        result = planner.plan_arrival(_request())
        assert result.status == MobilityStatus.UNAVAILABLE
        assert result.error_reason == MobilityErrorReason.NO_JOURNEY_FOUND
        assert not result.ok

    @pytest.mark.parametrize("error", [requests.exceptions.ConnectionError, requests.exceptions.Timeout])
    def test_unreachable_api_is_not_configured(self, planner, monkeypatch, error):
        def _raise(path, params):
            raise error("unavailable")
        monkeypatch.setattr(planner, "_get", _raise)

        result = planner.plan_arrival(_request())
        assert result.status == MobilityStatus.UNAVAILABLE
        assert result.error_reason == MobilityErrorReason.NOT_CONFIGURED

    def test_503_does_not_invent_an_efa_disabled_cause(self, planner, monkeypatch):
        def _raise(path, params):
            resp = _FakeResponse({}, status_code=503)
            raise requests.exceptions.HTTPError(response=resp)
        monkeypatch.setattr(planner, "_get", _raise)

        result = planner.plan_arrival(_request())
        assert result.status == MobilityStatus.UNAVAILABLE
        assert result.error_reason == MobilityErrorReason.HTTP_ERROR

    def test_422_does_not_invent_an_ambiguous_location_cause(self, planner, monkeypatch):
        def _raise(path, params):
            resp = _FakeResponse({}, status_code=422)
            raise requests.exceptions.HTTPError(response=resp)
        monkeypatch.setattr(planner, "_get", _raise)

        result = planner.plan_arrival(_request())
        assert result.error_reason == MobilityErrorReason.HTTP_ERROR

    def test_invalid_json_is_invalid_response(self, planner, monkeypatch):
        def invalid_json(path, params):
            raise requests.exceptions.JSONDecodeError("invalid", "<html>", 0)
        monkeypatch.setattr(planner, "_get", invalid_json)
        assert planner.plan_arrival(_request()).error_reason == MobilityErrorReason.INVALID_RESPONSE

    def test_aware_arrival_target_converts_to_berlin(self, planner, monkeypatch):
        captured = {}
        def query(path, params):
            captured.update(params)
            return _journeys_payload([_leg()])
        monkeypatch.setattr(planner, "_get", query)
        request = replace(_request(), arrive_by=datetime(2027, 3, 1, 11, tzinfo=timezone.utc))
        assert planner.plan_arrival(request).ok
        assert captured["at"] == "2027-03-01T11:55:00"

    @pytest.mark.parametrize("changes", [
        {"arrive_by": None}, {"arrive_by": "2027-03-01T12:00:00"},
        {"arrival_buffer_minutes": -1}, {"arrival_buffer_minutes": "5"},
        {"arrival_buffer_minutes": True}, {"arrival_buffer_minutes": 10**20},
    ])
    def test_invalid_request_never_calls_api(self, planner, monkeypatch, changes):
        def unexpected(*args, **kwargs):
            pytest.fail("Invalid request must not call the API")
        monkeypatch.setattr(planner, "_get", unexpected)
        result = planner.plan_arrival(replace(_request(), **changes))
        assert result.error_reason == MobilityErrorReason.INVALID_REQUEST

    def test_not_configured_when_base_url_empty(self, tmp_path):
        cfg = _FakeConfig({"mobility": {"base_url": "", "db_path": str(tmp_path / "m.db")}})
        empty_planner = MobilityPlanner(cfg)
        result = empty_planner.plan_arrival(_request())
        assert result.status == MobilityStatus.UNAVAILABLE
        assert result.error_reason == MobilityErrorReason.NOT_CONFIGURED

    def test_missing_origin_reports_not_configured(self, planner):
        req = MobilityRequest(
            person_id="test_person_no_origin",
            purpose="test_purpose",
            destination_id="de:08115:5678",
            arrive_by=datetime(2027, 3, 1, 12, 0, 0),
        )
        result = planner.plan_arrival(req)
        assert result.status == MobilityStatus.UNAVAILABLE
        assert result.error_reason == MobilityErrorReason.NOT_CONFIGURED

    @pytest.mark.parametrize("url", ["${VVS_API_URL}", "http://${VVS_HOST}:8090", "not-a-url", "ftp://example.invalid"])
    def test_unresolved_or_invalid_url_is_not_configured(self, tmp_path, url):
        cfg = _FakeConfig({"mobility": {"base_url": url, "api_key": "${VVS_API_KEY}", "db_path": str(tmp_path / "m.db")}})
        instance = MobilityPlanner(cfg)
        assert instance.plan_arrival(_request()).error_reason == MobilityErrorReason.NOT_CONFIGURED
        assert "X-API-Key" not in instance._session.headers


class TestPrivacyGate:
    def test_remote_tool_blocked_in_privacy_lock(self, planner, monkeypatch):
        monkeypatch.setattr(planner, "_get", lambda path, params: _journeys_payload([_leg()]))
        gate = get_privacy_gate()
        gate.enter(PrivacyMode.PRIVACY_LOCK)
        try:
            result = planner.plan_arrival(_request())
            assert result.status == MobilityStatus.UNAVAILABLE
            assert result.error_reason == MobilityErrorReason.PRIVACY_BLOCKED
        finally:
            gate.exit()

    def test_remote_tool_allowed_in_plain_privacy_mode(self, planner, monkeypatch):
        """core/privacy_gate.py's own docstring: REMOTE_TOOL is deliberately
        left allowed under plain PRIVACY — only PRIVACY_LOCK closes it."""
        monkeypatch.setattr(planner, "_get", lambda path, params: _journeys_payload([_leg()]))
        gate = get_privacy_gate()
        gate.enter(PrivacyMode.PRIVACY)
        try:
            result = planner.plan_arrival(_request())
            assert result.ok
        finally:
            gate.exit()


class TestPersonProfile:
    def test_default_profile_is_conservative(self, planner):
        profile = planner.get_profile("unconfigured_person")
        assert profile["allowed_alone"] is False

    def test_extra_buffer_minutes_shifts_query_target(self, planner, monkeypatch):
        planner.set_profile("test_person", extra_buffer_minutes=10)
        captured = {}

        def _capture_get(path, params):
            captured["params"] = params
            return _journeys_payload([_leg()])

        monkeypatch.setattr(planner, "_get", _capture_get)
        planner.plan_arrival(_request())

        # default_arrival_buffer(5, from request) + profile extra(10) = 15
        requested_at = datetime.fromisoformat(captured["params"]["at"])
        assert requested_at == datetime(2027, 3, 1, 11, 45, 0)
