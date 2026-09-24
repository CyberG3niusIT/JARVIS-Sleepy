"""School travel requirements use only synthetic timetable data."""

from datetime import date, datetime

import pytest

from core.school_db import SchoolDB


DAY = date(2030, 1, 7)  # Monday; synthetic fixture date.


@pytest.fixture
def school(tmp_path):
    return SchoolDB({"school.db_path": str(tmp_path / "school.db")})


def event(purpose, hour, minute=0):
    return {"person_id": "synthetic-person", "purpose": purpose,
            "event_time": datetime(2030, 1, 7, hour, minute)}


def periods(school):
    first = school.add_regular_period("synthetic-person", 0, "08:00", "12:00")
    school.add_regular_period("synthetic-person", 0, "14:00", "16:00")
    return first


def test_unknown_rules_emit_only_arrival(school):
    periods(school)
    assert school.travel_events(DAY) == [event("school_arrival", 8)]


def test_pickup_uses_resolved_override_end(school):
    periods(school)
    school.add_special_rule("pickup_required", "true", person_id="synthetic-person")
    school.add_override(DAY.isoformat(), "school_end", "15:20", person_id="synthetic-person")
    assert school.travel_events(DAY) == [event("school_arrival", 8), event("school_pickup", 15, 20)]


def test_independent_return_and_explicit_midday(school):
    first = periods(school)
    school.add_special_rule("independent_return_allowed", "true", person_id="synthetic-person")
    assert school.travel_events(DAY) == [event("school_arrival", 8), event("school_return", 16)]
    school.add_travel_requirement("synthetic-person", "school_return_midday", first)
    assert school.travel_events(DAY) == [event("school_arrival", 8), event("school_return_midday", 12), event("school_return", 16)]


@pytest.mark.parametrize("permission", [None, "false"])
def test_midday_requires_permission(school, permission):
    first = periods(school)
    school.add_travel_requirement("synthetic-person", "school_return_midday", first)
    if permission:
        school.add_special_rule("independent_return_allowed", permission, person_id="synthetic-person")
    assert school.travel_events(DAY) == [event("school_arrival", 8)]


def test_canceled_day_suppresses_all_events(school):
    first = periods(school)
    school.add_travel_requirement("synthetic-person", "school_return_midday", first)
    school.add_special_rule("independent_return_allowed", "true", person_id="synthetic-person")
    school.add_override(DAY.isoformat(), "canceled", "true", person_id="synthetic-person")
    assert school.travel_events(DAY) == []


def test_shortened_day_drops_midday_after_school_end(school):
    first = periods(school)
    school.add_travel_requirement("synthetic-person", "school_return_midday", first)
    school.add_special_rule("independent_return_allowed", "true", person_id="synthetic-person")
    school.add_override(DAY.isoformat(), "school_end", "11:00", person_id="synthetic-person")
    assert school.travel_events(DAY) == [event("school_arrival", 8), event("school_return", 11)]


def test_pickup_takes_precedence_over_independent_final_return(school):
    periods(school)
    school.add_special_rule("independent_return_allowed", "true", person_id="synthetic-person")
    school.add_special_rule("pickup_required", "true", person_id="synthetic-person")
    assert school.travel_events(DAY) == [event("school_arrival", 8), event("school_pickup", 16)]


def test_optional_period_does_not_change_arrival_or_return(school):
    periods(school)
    school.add_regular_period("synthetic-person", 0, "07:00", "07:30", mandatory=False)
    school.add_regular_period("synthetic-person", 0, "17:00", "18:00", mandatory=False)
    school.add_special_rule("independent_return_allowed", "true", person_id="synthetic-person")
    assert school.travel_events(DAY) == [event("school_arrival", 8), event("school_return", 16)]


def test_period_weekday_controls_extra_requirement(school):
    first = periods(school)
    school.add_travel_requirement("synthetic-person", "school_return_midday", first)
    school.add_special_rule("independent_return_allowed", "true", person_id="synthetic-person")
    assert school.travel_events(date(2030, 1, 8)) == []


def test_afternoon_arrival_uses_selected_period_start(school):
    first = periods(school)
    afternoon = school.resolve_day("synthetic-person", DAY).periods[-1]["id"]
    school.add_special_rule("independent_return_allowed", "true", person_id="synthetic-person")
    school.add_travel_requirement("synthetic-person", "school_return_midday", first)
    school.add_travel_requirement("synthetic-person", "school_arrival_afternoon", afternoon)
    assert school.travel_events(DAY) == [event("school_arrival", 8), event("school_return_midday", 12),
                                         event("school_arrival_afternoon", 14), event("school_return", 16)]


def test_approximate_end_and_note_survive_resolution(school):
    periods(school)
    school.add_special_rule("school_end", "15:45", person_id="synthetic-person", note="Synthetic release condition")
    school.add_special_rule("school_end_approximate", "true", person_id="synthetic-person")
    status = school.resolve_day("synthetic-person", DAY)
    assert status.school_end_approximate is True
    assert status.note == "Synthetic release condition"
    school.add_override(DAY.isoformat(), "school_end_approximate", "false", person_id="synthetic-person")
    assert school.resolve_day("synthetic-person", DAY).school_end_approximate is False


@pytest.mark.parametrize("case", ["missing", "other_person", "optional", "purpose"])
def test_invalid_requirement_rejected(school, case):
    person = "other-person" if case == "other_person" else "synthetic-person"
    period_id = school.add_regular_period(person, 0, "08:00", "12:00", mandatory=case != "optional")
    with pytest.raises(ValueError):
        school.add_travel_requirement("synthetic-person", "unknown" if case == "purpose" else "school_return_midday",
                                      "missing-id" if case == "missing" else period_id)
