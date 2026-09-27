"""School owns school-day facts; Mobility owns pickup travel planning."""

from __future__ import annotations

import json
from datetime import date, datetime

from core.base_skill import BaseSkill
from core.mobility_contract import MobilityRequest
from core.people_manager import get_people_manager
from core.school_db import DayStatus, get_school_db


class SchoolSkill(BaseSkill):
    """Resolve school questions against the speaker's existing contacts."""

    def initialize(self) -> bool:
        self._db = None
        self.enabled = self.config.get("school.enabled", True)
        if not self.enabled:
            return False
        for pattern, handler in (
            ("wann hat {person} heute aus", self.report_school_end),
            ("wann endet die schule für {person} heute", self.report_school_end),
            ("wann muss {person} heute zur schule los", self.report_school_departure),
            ("muss ich {person} heute abholen", self.report_today_status),
            ("wann muss ich los um {person} abzuholen", self.report_pickup_departure),
            ("wann muss ich los um {person} heute abzuholen", self.report_pickup_departure),
        ):
            self.register_intent(pattern, handler, priority=9)
        return True

    def handle_intent(self, intent: str, entities: dict) -> str | None:
        if intent in self.intents:
            return self.intents[intent]["handler"](entities or {})
        return None

    @property
    def db(self):
        if self._db is None:
            self._db = get_school_db(self.config)
        return self._db

    def get_day_status(self, person_id: str, on_date: date | None = None) -> DayStatus:
        """Return the authoritative school-day resolution."""
        return self.db.resolve_day(person_id, on_date or date.today())

    def pickup_required(self, person_id: str, on_date: date | None = None) -> bool | None:
        """Return None when the pickup rule is unknown."""
        return self.get_day_status(person_id, on_date).pickup_required

    def build_mobility_request(
        self, person_id: str, destination_id: str, on_date: date | None = None,
        arrival_buffer_minutes: int = 5,
    ) -> MobilityRequest | None:
        """Use the child's school end and the current speaker's travel origin."""
        status = self.get_day_status(person_id, on_date)
        if status.canceled or status.school_end is None:
            return None
        event_time = datetime.combine(status.date, status.school_end)
        return MobilityRequest(
            person_id=self.current_user, purpose="school_pickup",
            destination_id=destination_id, arrive_by=event_time,
            event_time=event_time, arrival_buffer_minutes=arrival_buffer_minutes,
        )

    def _resolve_person(self, entities: dict | None) -> tuple[dict | None, str]:
        manager = get_people_manager()
        if manager is None:
            return None, "Die Personenverwaltung ist noch nicht verfügbar."
        people = manager.get_all_people(user_id=self.current_user)
        explicit = (entities or {}).get("person")
        if explicit:
            query = str(explicit).strip().casefold()
            matches = [p for p in people if p["name"].casefold() == query
                       or p["person_id"] == explicit]
        else:
            default = self.config.get("school.default_person_id")
            matches = [p for p in people if p["person_id"] == default] if default else []
        if len(matches) != 1:
            return None, ("Der Name ist nicht eindeutig. Bitte nenne den vollständigen Namen."
                          if matches else "Für welches bekannte Kind soll ich das prüfen? Den Namen kann ich nicht zuordnen.")
        return matches[0], ""

    def report_school_end(self, entities: dict | None = None) -> str:
        """Report school end even when the pickup rule is not configured."""
        person, error = self._resolve_person(entities)
        if person is None:
            return self.respond(error)
        try:
            status = self.get_day_status(person["person_id"])
        except ValueError:
            return self.respond("Die hinterlegten Schuldaten sind ungültig. Bitte prüfe den Eintrag.")
        if status.canceled:
            return self.respond("Der Unterricht fällt heute aus.")
        if status.school_end is None:
            return self.respond("Für heute ist kein Schulende hinterlegt.")
        if status.school_end_approximate:
            if status.note:
                return self.respond(f"{person['name']}: {status.note}")
            return self.respond(f"{person['name']} hat heute ungefähr um {status.school_end:%H:%M} aus.")
        return self.respond(f"{person['name']} hat heute um {status.school_end:%H:%M} aus.")

    def report_today_status(self, entities: dict | None = None) -> str:
        """Report the resolved pickup rule, preserving unknown state."""
        person, error = self._resolve_person(entities)
        if person is None:
            return self.respond(error)
        try:
            status = self.get_day_status(person["person_id"])
        except ValueError:
            return self.respond("Die hinterlegten Schuldaten sind ungültig. Bitte prüfe den Eintrag.")
        if status.canceled:
            return self.respond("Der Unterricht fällt heute aus.")
        if status.pickup_required is None:
            return self.respond("Für heute ist keine Abholregel hinterlegt.")
        if not status.pickup_required:
            return self.respond(f"Du musst {person['name']} heute nicht abholen.")
        if status.school_end:
            end = f" gegen {status.school_end:%H:%M}" if status.school_end_approximate else f" um {status.school_end:%H:%M}"
        else:
            end = " zu einer noch unbekannten Uhrzeit"
        return self.respond(f"Du musst {person['name']} heute{end} abholen.")

    def report_school_departure(self, entities: dict | None = None) -> str:
        """Ask Mobility for the departure serving today's resolved school start."""
        person, error = self._resolve_person(entities)
        if person is None:
            return self.respond(error)
        try:
            status = self.get_day_status(person["person_id"])
            event = next((item for item in self.db.travel_events(status.date)
                          if item["person_id"] == person["person_id"]
                          and item["purpose"] == "school_arrival"), None)
        except ValueError:
            return self.respond("Die hinterlegten Schuldaten sind ungültig. Bitte prüfe den Eintrag.")
        if status.canceled:
            return self.respond("Der Unterricht fällt heute aus.")
        if event is None:
            return self.respond("Für heute ist kein Schulbeginn hinterlegt.")
        # SkillManager loads this module as ``skills.system.mobility``.
        from skills.system.mobility import MobilitySkill

        mobility = MobilitySkill(self.config, self.conversation, self.tts, self.responses)
        mobility.initialize()
        result = mobility.plan_school_event(event)
        return self.respond(f"Für {person['name']}: {mobility.format_result(result)}")

    def report_pickup_departure(self, entities: dict | None = None) -> str:
        """Plan only an explicit departure request with known pickup facts."""
        person, error = self._resolve_person(entities)
        if person is None:
            return self.respond(error)
        try:
            status = self.get_day_status(person["person_id"])
        except ValueError:
            return self.respond("Die hinterlegten Schuldaten sind ungültig. Bitte prüfe den Eintrag.")
        if status.canceled:
            return self.respond("Der Unterricht fällt heute aus.")
        if status.pickup_required is None:
            return self.respond("Für heute ist keine Abholregel hinterlegt.")
        if not status.pickup_required:
            return self.respond("Heute ist keine Abholung erforderlich.")
        if status.school_end is None:
            return self.respond("Für heute ist kein Schulende hinterlegt.")
        destinations = self.config.get("school.destinations", {}) or {}
        if isinstance(destinations, str):
            try:
                destinations = json.loads(destinations)
            except ValueError:
                destinations = {}
        destination = destinations.get(person["person_id"]) if isinstance(destinations, dict) else None
        if not isinstance(destination, str) or not destination.strip():
            return self.respond("NOT_CONFIGURED: Für diese Person ist kein Schulziel konfiguriert.")
        # SkillManager loads this module as ``skills.system.mobility``.
        from skills.system.mobility import MobilitySkill

        event_time = datetime.combine(status.date, status.school_end)
        request = MobilityRequest(
            person_id=self.current_user, purpose="school_pickup",
            destination_id=destination, arrive_by=event_time, event_time=event_time,
            arrival_buffer_minutes=self.config.get("mobility.default_arrival_buffer_minutes", 5),
        )
        mobility = MobilitySkill(self.config, self.conversation, self.tts, self.responses)
        mobility.initialize()
        result = mobility.report_result(mobility.plan(request))
        if status.school_end_approximate:
            result += f" Das Schulende ist ungefähr um {status.school_end:%H:%M}."
        return result
