"""Unit tests for core/school_db.py.

Uses a real temp-file SQLite DB (same convention as
tests/unit/test_memory_manager_tiers.py) — no mocking of the resolver
logic itself, since the priority stack is exactly what's under test.

All person/date data here is synthetic per task brief section 16 ("Nutze
synthetische Testpersonen und Testorte").
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.school_db import SchoolDB, Provenance


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


@pytest.fixture
def db(tmp_path):
    cfg = _FakeConfig({"school": {"db_path": str(tmp_path / "school.db")}})
    return SchoolDB(cfg)


PERSON = "test_child_alpha"
MONDAY = date(2027, 3, 1)   # synthetic date, known weekday=0 (Monday)
assert MONDAY.weekday() == 0


class TestRegularSchedule:
    def test_mandatory_period_sets_school_end(self, db):
        db.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30", mandatory=True)
        status = db.resolve_day(PERSON, MONDAY)
        assert status.school_end.strftime("%H:%M") == "12:30"
        assert status.provenance == Provenance.REGULAR_SCHEDULE

    def test_voluntary_period_does_not_extend_school_end(self, db):
        """A voluntary ('freiwillig') period after the mandatory block must
        NOT push school_end later — this is the exact scenario called out
        in task brief section 4."""
        db.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30", mandatory=True)
        db.add_regular_period(PERSON, weekday=0, start_time="12:30", end_time="13:15",
                               label="AG (freiwillig)", mandatory=False)
        status = db.resolve_day(PERSON, MONDAY)
        assert status.school_end.strftime("%H:%M") == "12:30"

    def test_no_schedule_for_weekday_leaves_school_end_none(self, db):
        db.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30")
        sunday = date(2027, 2, 28)
        assert sunday.weekday() == 6
        status = db.resolve_day(PERSON, sunday)
        assert status.school_end is None


class TestPickupRequirement:
    def test_pickup_required_none_when_unconfigured(self, db):
        db.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30")
        status = db.resolve_day(PERSON, MONDAY)
        assert status.pickup_required is None  # must NOT default to False silently

    def test_pickup_required_true_via_special_rule(self, db):
        db.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30")
        db.add_special_rule(rule_type="pickup_required", value="true", person_id=PERSON)
        status = db.resolve_day(PERSON, MONDAY)
        assert status.pickup_required is True
        assert status.provenance == Provenance.SPECIAL_RULE

    def test_pickup_not_required_via_special_rule(self, db):
        db.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30")
        db.add_special_rule(rule_type="pickup_required", value="false", person_id=PERSON)
        status = db.resolve_day(PERSON, MONDAY)
        assert status.pickup_required is False


class TestIndependentReturn:
    def test_independent_return_allowed_via_special_rule(self, db):
        db.add_special_rule(rule_type="independent_return_allowed", value="true", person_id=PERSON)
        status = db.resolve_day(PERSON, MONDAY)
        assert status.independent_return_allowed is True


class TestOverridePriority:
    """Verifies the exact stack from task brief section 5:
    override > school_message (confirmed) > special_rule > regular_schedule.
    """

    def test_override_beats_everything(self, db):
        db.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30")
        db.add_special_rule(rule_type="school_end", value="13:00", person_id=PERSON)
        db.add_day_event(event_date=MONDAY.isoformat(), rule_type="school_end", value="13:30",
                          person_id=PERSON, confirmed=True, source="school office")
        db.add_override(event_date=MONDAY.isoformat(), rule_type="school_end", value="11:00",
                         person_id=PERSON, note="Arzttermin, früher abgeholt")

        status = db.resolve_day(PERSON, MONDAY)
        assert status.school_end.strftime("%H:%M") == "11:00"
        assert status.provenance == Provenance.OVERRIDE

    def test_confirmed_school_message_beats_special_rule_but_not_override(self, db):
        db.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30")
        db.add_special_rule(rule_type="school_end", value="13:00", person_id=PERSON)
        db.add_day_event(event_date=MONDAY.isoformat(), rule_type="school_end", value="13:30",
                          person_id=PERSON, confirmed=True, source="school office")

        status = db.resolve_day(PERSON, MONDAY)
        assert status.school_end.strftime("%H:%M") == "13:30"
        assert status.provenance == Provenance.SCHOOL_MESSAGE

    def test_unconfirmed_school_message_does_not_change_resolution(self, db):
        """An unverified message must never silently change what's decided —
        task brief section 6 concept: only a *confirmed* message outranks
        a special rule."""
        db.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30")
        db.add_special_rule(rule_type="school_end", value="13:00", person_id=PERSON)
        db.add_day_event(event_date=MONDAY.isoformat(), rule_type="school_end", value="09:00",
                          person_id=PERSON, confirmed=False, source="unverified rumour")

        status = db.resolve_day(PERSON, MONDAY)
        assert status.school_end.strftime("%H:%M") == "13:00"
        assert status.provenance == Provenance.SPECIAL_RULE
        # but the unconfirmed event is still visible for a human to check:
        events = db.list_day_events(PERSON, MONDAY)
        assert any(e["rule_type"] == "school_end" and not e["confirmed"] for e in events)

    def test_special_rule_beats_regular_schedule(self, db):
        db.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30")
        db.add_special_rule(rule_type="school_end", value="10:00", person_id=PERSON,
                             note="Mittwochsregelung o.ä.")
        status = db.resolve_day(PERSON, MONDAY)
        assert status.school_end.strftime("%H:%M") == "10:00"


class TestCanceled:
    def test_override_can_cancel_school(self, db):
        db.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30")
        db.add_override(event_date=MONDAY.isoformat(), rule_type="canceled", value="true", person_id=PERSON,
                         note="Lehrerfortbildung, unterrichtsfrei")
        status = db.resolve_day(PERSON, MONDAY)
        assert status.canceled is True


class TestNoHardcodedPersonalData:
    """Guards task brief section 6: the DB path must default outside the
    repository checkout, and the module must contain no seeded rows
    (INSERT statements are only ever built from caller-supplied
    arguments, never literal data baked into the module)."""

    def test_default_db_path_is_outside_repo_checkout(self):
        import core.school_db as mod
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(mod.__file__))))
        cfg = _FakeConfig({})  # no school.db_path set -> falls back to default
        default_path = cfg.get("school.db_path", "/home/alex/jarvis-data/data/school.db")
        assert not str(default_path).startswith(repo_root), (
            "school.db_path default must live outside the git checkout"
        )

    def test_module_source_has_no_seeded_insert_statements(self):
        import core.school_db as mod
        src = open(mod.__file__, encoding="utf-8").read()
        # The only INSERT statements in this module must be the five
        # parameterized writer methods (add_regular_period, add_special_rule,
        # add_day_event, add_override, add_travel_requirement) — never a literal seeded row. Every
        # INSERT must be paired with a "VALUES (?" placeholder list.
        insert_count = src.count("INSERT INTO")
        values_placeholder_count = src.count("VALUES (?")
        assert insert_count == 5, f"Expected 5 INSERT statements, found {insert_count}"
        assert values_placeholder_count == 5, (
            f"Expected {insert_count} parameterized VALUES clauses, found {values_placeholder_count}"
        )
