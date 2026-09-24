"""Verifies the School -> Mobility contract itself (task brief section 8):
School builds a MobilityRequest expressing *intent* (arrive_by + purpose),
never a line/departure time, and Mobility's plan_arrival() accepts it
without either module importing the other's internals.

core/mobility_contract.py is imported by both core/school_db.py-adjacent
code (skills/personal/school/skill.py) and core/mobility_planner.py, but
neither of those two imports the other — this test also acts as a guard
against that (task brief section 8: "keine zyklischen Imports").
"""

import ast
import os
import sys
from datetime import date, datetime, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.school_db import SchoolDB
from core.mobility_contract import MobilityRequest, MobilityStatus, MobilityErrorReason
from core.mobility_planner import MobilityPlanner


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


PERSON = "test_child_alpha"
DESTINATION = "de:08115:1234"
MONDAY = date(2027, 3, 1)
assert MONDAY.weekday() == 0


def _build_request(school: SchoolDB, on_date=MONDAY) -> MobilityRequest:
    """Mirrors skills/personal/school/skill.py's build_mobility_request()
    without needing a full BaseSkill/Conversation/TTS stack in the test."""
    status = school.resolve_day(PERSON, on_date)
    assert status.school_end is not None
    arrive_by = datetime.combine(status.date, status.school_end)
    return MobilityRequest(
        person_id=PERSON,
        purpose="school_pickup",
        destination_id=DESTINATION,
        arrive_by=arrive_by,
        arrival_buffer_minutes=5,
    )


def test_contract_request_carries_intent_not_a_transit_plan(tmp_path):
    school = SchoolDB(_FakeConfig({"school": {"db_path": str(tmp_path / "school.db")}}))
    school.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30")

    request = _build_request(school)

    assert request.purpose == "school_pickup"
    assert request.arrive_by == datetime(2027, 3, 1, 12, 30)
    # the contract must NOT expose a line/bus/route — that's Mobility's job
    assert not hasattr(request, "line")
    assert not hasattr(request, "route")


def test_contract_flows_into_mobility_planner(tmp_path, monkeypatch):
    school = SchoolDB(_FakeConfig({"school": {"db_path": str(tmp_path / "school.db")}}))
    school.add_regular_period(PERSON, weekday=0, start_time="08:00", end_time="12:30")
    request = _build_request(school)
    # origin isn't known to School (by design) — the request as School
    # builds it has no origin_id; a caller (e.g. skills/system/mobility)
    # is responsible for supplying one, or the person's profile default.
    object.__setattr__(request, "origin_id", "de:08115:5678")

    planner = MobilityPlanner(_FakeConfig({
        "mobility": {"base_url": "http://127.0.0.1:8090", "db_path": str(tmp_path / "mobility.db")}
    }))
    monkeypatch.setattr(planner, "_get", lambda path, params: {
        "journeys": [{
            "legs": [{
                "duration_seconds": 600,
                "origin": {"planned": "2027-03-01T12:00:00+01:00", "estimated": None},
                "destination": {"planned": "2027-03-01T12:25:00+01:00", "estimated": None, "delay_seconds": None},
                "transport": {"line": "168", "product_class": 5},
                "infos": [],
            }],
        }],
        "system_messages": [],
    })

    result = planner.plan_arrival(request)

    assert result.ok
    assert result.status == MobilityStatus.SCHEDULE_ONLY
    assert result.leave_at == datetime(2027, 3, 1, 12, 0, 0)


def test_no_school_end_produces_no_request():
    """skills/personal/school/skill.py.build_mobility_request() returns
    None when there's nothing to plan a trip for — checked directly
    against the source text (readable, and doesn't need a full
    BaseSkill/Conversation/TTS stack just to import the module)."""
    src_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "skills", "personal", "school", "skill.py",
    )
    src = open(src_path, encoding="utf-8").read()
    assert "def build_mobility_request" in src
    # Extract just that method's body (next "def " at the same indent ends it)
    start = src.index("def build_mobility_request")
    rest = src[start:]
    end = rest.index("\n    def ", 1)
    body = rest[:end]
    assert "return None" in body
    assert "status.school_end is None" in body


class TestNoCyclicImports:
    """Checks actual import statements (ast), not substring occurrences —
    core/mobility_planner.py's own docstring legitimately mentions
    core/school_db.py as documentation, that must not fail this check."""

    @staticmethod
    def _imported_modules(path: str) -> set[str]:
        tree = ast.parse(open(path, encoding="utf-8").read())
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
        return modules

    def test_mobility_planner_does_not_import_school(self):
        import core.mobility_planner as mod
        modules = self._imported_modules(mod.__file__)
        assert not any("school" in m for m in modules), modules

    def test_school_db_does_not_import_mobility_planner(self):
        import core.school_db as mod
        modules = self._imported_modules(mod.__file__)
        assert not any("mobility" in m for m in modules), modules
