"""Mobility Skill

Thin voice/LLM-facing wrapper around core/mobility_planner.py. General
purpose per task brief section 7 — works for school, appointments,
work, anything with a MobilityRequest, not just school pickups.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from core.base_skill import BaseSkill
from core.mobility_planner import get_mobility_planner
from core.mobility_contract import MobilityRequest, MobilityStatus


class MobilitySkill(BaseSkill):
    """General journey planning: arrive-by / leave-at."""

    def initialize(self) -> bool:
        self._planner = None

        self.enabled = self.config.get("mobility.enabled", True)
        if not self.enabled:
            return False
        for pattern in ("wann muss ich los", "wann muss ich losfahren",
                        "wann muss ich aufbrechen"):
            self.register_intent(pattern, self.report_departure_time)

        return True

    def handle_intent(self, intent: str, entities: dict) -> str | None:
        if intent in self.intents:
            return self.intents[intent]["handler"](entities or {})
        return None

    @property
    def planner(self):
        if self._planner is None:
            self._planner = get_mobility_planner(self.config)
        return self._planner

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, request: MobilityRequest):
        """Delegate straight to the planner. Kept as a thin passthrough so
        callers (School, other skills) depend on the skill's stable
        surface rather than reaching into core.mobility_planner directly —
        but the contract itself is defined in core/mobility_contract.py,
        not here."""
        return self.planner.plan_arrival(request)

    def plan_school_event(self, event: dict):
        """Plan a School-derived departure through Mobility-owned route rules."""
        return self.planner.plan_school_event(event)

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    def report_departure_time(self, entities: dict = None) -> str:
        entities = entities or {}
        person_id = self.current_user
        destination_id = entities.get("destination") or self.config.get("mobility.default_destination_id")
        if not destination_id:
            return self.respond("Wohin soll die Fahrt gehen? Ich kenne kein Standardziel.")

        arrive_by_minutes = entities.get("in_minutes")
        arrive_by = entities.get("arrive_by")
        if not isinstance(arrive_by, datetime):
            try:
                minutes = int(arrive_by_minutes)
            except (TypeError, ValueError):
                return self.respond("Wann möchtest du am Ziel ankommen?")
            if minutes <= 0 or minutes > 10080:
                return self.respond("Bitte nenne eine zukünftige Ankunftszeit innerhalb der nächsten Woche.")
            arrive_by = datetime.now() + timedelta(minutes=minutes)

        request = MobilityRequest(
            person_id=person_id,
            purpose="ad_hoc",
            destination_id=destination_id,
            arrive_by=arrive_by,
        )
        return self.report_result(self.plan(request))

    @staticmethod
    def format_result(result) -> str:
        """Render a planner result without speaking or upgrading its quality."""
        if not result.ok:
            return result.message or "Ich konnte keine Verbindung ermitteln."

        leave_str = result.leave_at.strftime("%H:%M")
        if result.status == MobilityStatus.REALTIME:
            delay_note = f", {result.delay_minutes} Minuten Verspätung" if result.delay_minutes else ""
            return f"Du solltest um {leave_str} los{delay_note}."
        if result.status == MobilityStatus.DEGRADED:
            return f"Du solltest um {leave_str} los; Echtzeitdaten liegen nur teilweise vor."
        return f"Nach Fahrplan solltest du um {leave_str} los (ohne Echtzeitdaten)."

    def report_result(self, result) -> str:
        """Speak a rendered planner result without upgrading its data quality."""
        return self.respond(self.format_result(result))
