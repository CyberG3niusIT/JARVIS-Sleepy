"""Real routing, contact and school stores; HTTP is synthetic, never live VVS."""

from datetime import date, datetime, time
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import people_manager
from core.conversation_router import ConversationRouter
from core.mobility_planner import MobilityPlanner
from core.mobility_contract import MobilityStatus
from core.people_manager import PeopleManager
from core.school_db import SchoolDB
from core.skill_manager import SkillManager
from skills.personal.school.skill import SchoolSkill
from skills.system.mobility.skill import MobilitySkill


@pytest.fixture
def flow(tmp_path, monkeypatch):
    config = {
        "people.db_path": str(tmp_path / "people.db"),
        "school.db_path": str(tmp_path / "school.db"),
        "mobility.db_path": str(tmp_path / "mobility.db"),
        "mobility.base_url": "http://127.0.0.1:8088",
    }
    people = PeopleManager(config)
    monkeypatch.setattr(people_manager, "_instance", people)
    child = people.add_person("TestkindAlpha", user_id="test_parent")
    people.add_person("TestkindBeta", user_id="other_parent")
    config["school.destinations"] = json.dumps({child: "synthetic-school-stop"})
    conversation = SimpleNamespace(current_user="test_parent")
    school = SchoolSkill(config, conversation, Mock(), Mock())
    school.initialize()
    school._db = SchoolDB(config)
    school.db.add_regular_period(child, date.today().weekday(), "08:00", "13:00")
    school.db.add_special_rule("pickup_required", "true", person_id=child)
    planner = MobilityPlanner(config)
    planner.set_profile("test_parent", default_origin_id="synthetic-adult-origin")
    monkeypatch.setattr("skills.system.mobility.skill.get_mobility_planner", lambda config: planner)
    # Skip costly embedding-model startup; exercise real pattern compilation,
    # matching, execution and handlers with a minimal SkillManager shell.
    manager = SkillManager.__new__(SkillManager)
    manager.skills = {"school": school}
    manager.skill_metadata = {}
    manager.intent_patterns = []
    manager.logger = Mock()
    manager.config = config
    manager.conversation = conversation
    manager.tts = Mock()
    manager.responses = Mock()
    manager._last_match_info = None
    manager._privacy_gate = None
    manager._register_skill_intents("school", school)
    monkeypatch.setattr(manager, "_check_pending_confirmations", lambda text: None)
    monkeypatch.setattr(manager, "_emit_skill_audit_event", lambda *args, **kwargs: None)
    return manager, school, planner, people, child, config


def test_exact_school_questions_do_not_request_routes(flow, monkeypatch):
    manager, school, planner, people, child, config = flow
    http = Mock(side_effect=AssertionError("School facts must not query routes"))
    monkeypatch.setattr(planner._session, "get", http)
    assert "13:00" in manager.execute_intent("Wann hat TestkindAlpha heute aus?")
    assert "13:00" in manager.execute_intent("Muss ich TestkindAlpha heute abholen?")
    http.assert_not_called()


def test_name_school_to_mobility_http_contract_mock_only(flow, monkeypatch):
    manager, school, planner, people, child, config = flow
    today = date.today().isoformat()
    response = Mock(status_code=200)
    response.json.return_value = {"journeys": [{"legs": [{
        "origin": {"planned": today + "T12:20:00", "name": "Synthetic origin"},
        "destination": {"planned": today + "T12:45:00", "name": "Synthetic school"},
        "transport": {"line": "TEST", "product_class": 5},
    }]}]}
    http = Mock(return_value=response)
    monkeypatch.setattr(planner._session, "get", http)
    answer = manager.execute_intent("Wann muss ich los, um TestkindAlpha abzuholen?")
    assert "12:20" in answer
    assert "ohne Echtzeitdaten" in answer
    params = http.call_args.kwargs["params"]
    assert params["from"] == "synthetic-adult-origin"
    assert params["to"] == "synthetic-school-stop"
    assert school.build_mobility_request(child, "synthetic-school-stop").person_id == "test_parent"


@pytest.mark.parametrize("name", ["Unbekannt", "TestkindBeta"])
def test_explicit_unknown_or_other_user_never_falls_back(flow, name):
    manager, school, planner, people, child, config = flow
    config["school.default_person_id"] = child
    assert "nicht zuordnen" in manager.execute_intent(f"Wann hat {name} heute aus?")


def test_duplicate_name_requires_clarification(flow):
    manager, school, planner, people, child, config = flow
    people.add_person("TestkindAlpha", user_id="test_parent")
    assert "nicht eindeutig" in manager.execute_intent("Wann hat TestkindAlpha heute aus?")


def test_school_end_does_not_require_pickup_rule(flow):
    manager, school, planner, people, child, config = flow
    second = people.add_person("Testkind", user_id="test_parent")
    school.db.add_regular_period(second, date.today().weekday(), "08:00", "12:00")
    assert "12:00" in manager.execute_intent("Wann hat Testkind heute aus?")
    assert "keine Abholregel" in manager.execute_intent("Muss ich Testkind heute abholen?")


def test_approximate_school_end_is_not_spoken_as_exact(flow):
    manager, school, planner, people, child, config = flow
    school.db.add_special_rule("school_end_approximate", "true", person_id=child,
                               note="Herausgabe etwa 12:17.")
    answer = manager.execute_intent("Wann hat TestkindAlpha heute aus?")
    assert "Herausgabe etwa 12:17" in answer


@pytest.mark.parametrize("destinations", ["${JARVIS_SCHOOL_DESTINATIONS}", "[]", "bad json", {}])
def test_missing_destination_is_not_configured(flow, destinations):
    manager, school, planner, people, child, config = flow
    config["school.destinations"] = destinations
    assert "NOT_CONFIGURED" in manager.execute_intent("Wann muss ich los, um TestkindAlpha abzuholen?")


def test_generic_mobility_requires_arrival_time(flow):
    manager, school, planner, people, child, config = flow
    mobility = MobilitySkill(config, school.conversation, Mock(), Mock())
    mobility.initialize()
    answer = mobility.report_departure_time({"destination": "synthetic-stop"})
    assert "Wann möchtest du" in answer


def test_spoken_school_departure_resolves_person_and_calls_mobility(flow, monkeypatch):
    manager, school, planner, people, child, config = flow
    root = Path(__file__).resolve().parents[2]
    module_name = "skills.system.mobility"
    original_module = sys.modules.get(module_name)
    planner.plan_school_event = Mock(return_value=SimpleNamespace(
        ok=True, status=MobilityStatus.SCHEDULE_ONLY,
        leave_at=datetime.combine(date.today(), time(7, 25)),
        delay_minutes=None, message="",
    ))
    try:
        assert manager.load_skill(root / "skills" / "system" / "mobility")
        mobility_module = sys.modules[module_name]
        monkeypatch.setattr(mobility_module, "get_mobility_planner", lambda config: planner)
        result = manager.execute_intent("Wann muss TestkindAlpha heute zur Schule los?")
        assert mobility_module.MobilitySkill.__name__ == "MobilitySkill"
    finally:
        if original_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original_module

    assert "07:25" in result
    planner.plan_school_event.assert_called_once()
    event = planner.plan_school_event.call_args.args[0]
    assert event["person_id"] == child
    assert event["purpose"] == "school_arrival"


@pytest.mark.parametrize("value", ["treu", "unknown", "", "2"])
def test_invalid_pickup_rule_is_rejected(flow, value):
    manager, school, planner, people, child, config = flow
    with pytest.raises(ValueError, match="explicitly"):
        school.db.add_special_rule("pickup_required", value, person_id=child)


def test_invalid_time_is_rejected(flow):
    manager, school, planner, people, child, config = flow
    with pytest.raises(ValueError, match="HH:MM"):
        school.db.add_regular_period(child, 1, "8:00", "13:00")


def test_canceled_school_never_plans_pickup(flow, monkeypatch):
    manager, school, planner, people, child, config = flow
    school.db.add_override(date.today().isoformat(), "canceled", "true", person_id=child)
    http = Mock(side_effect=AssertionError("Canceled school cannot plan pickup"))
    monkeypatch.setattr(planner._session, "get", http)
    assert "fällt heute aus" in manager.execute_intent("Wann muss ich los, um TestkindAlpha abzuholen?")
    http.assert_not_called()


def test_no_pickup_never_plans(flow, monkeypatch):
    manager, school, planner, people, child, config = flow
    school.db.add_override(date.today().isoformat(), "pickup_required", "false", person_id=child)
    http = Mock(side_effect=AssertionError("No pickup cannot plan pickup"))
    monkeypatch.setattr(planner._session, "get", http)
    assert "keine Abholung" in manager.execute_intent("Wann muss ich los, um TestkindAlpha abzuholen?")
    http.assert_not_called()


@pytest.mark.parametrize("question", [
    "Wann hat TestkindAlpha heute aus?", "Muss ich TestkindAlpha heute abholen?",
    "Wann muss ich los, um TestkindAlpha abzuholen?",
])
def test_invalid_legacy_school_data_reports_error(flow, monkeypatch, question):
    manager, school, planner, people, child, config = flow
    with school.db._conn() as conn:
        conn.execute("UPDATE special_rules SET value = 'unknown' WHERE person_id = ?", (child,))
    http = Mock(side_effect=AssertionError("Invalid school facts cannot plan pickup"))
    monkeypatch.setattr(planner._session, "get", http)
    assert "Schuldaten sind ungültig" in manager.execute_intent(question)
    http.assert_not_called()


@pytest.mark.parametrize("question,expected", [
    ("Wann hat TestkindAlpha heute aus?", "13:00"),
    ("Muss ich TestkindAlpha heute abholen?", "abholen"),
    ("Wann muss ich los, um TestkindAlpha abzuholen?", "nicht konfiguriert"),
])
def test_conversation_router_school_flow(flow, question, expected):
    manager, school, planner, people, child, config = flow
    planner.base_url = ""
    router = ConversationRouter(
        skill_manager=manager, conversation=school.conversation,
        llm=SimpleNamespace(), config=config,
    )
    result = router.route(question)
    assert result.handled
    assert expected in result.text
