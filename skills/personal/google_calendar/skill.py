"""Calendar mutations reuse the existing skill confirmation chain."""
import re
import time

from core.base_skill import BaseSkill
from core.confirmation_matching import parse_confirmation
from core.privacy_gate import Capability, get_privacy_gate
from core.reminder_manager import ReminderManager


class GoogleCalendarSkill(BaseSkill):
    def initialize(self):
        self._pending_confirmation = None
        self.register_semantic_intent(
            examples=["Erstelle einen Termin morgen um 17 Uhr für den Einkauf",
                      "Trage einen Termin morgen früh für den Anruf ein",
                      "Trag morgen um 10 Uhr einen Testtermin ein"],
            handler=self.create_calendar_event, threshold=0.75)
        self.register_semantic_intent(
            examples=["Lösche den Termin Einkauf aus dem Kalender"],
            handler=self.delete_calendar_event, threshold=0.78)
        self.register_semantic_intent(
            examples=["Verschiebe den Termin Einkauf auf morgen um 17 Uhr"],
            handler=self.update_calendar_event, threshold=0.78)
        return True

    @property
    def manager(self):
        if hasattr(self, "_manager_ref"):
            return self._manager_ref
        from core.google_calendar import get_calendar_manager
        return get_calendar_manager()

    def _requester(self):
        user = getattr(self.conversation, "current_user", None)
        return user if isinstance(user, str) and user.strip() and user.casefold() not in {
            "__guest__", "guest", "unknown", "anonymous", "none", "__unknown__"} else None

    def request_write(self, action, payload):
        self._pending_confirmation = None
        mgr, user = self.manager, self._requester()
        if not user:
            return "Bitte wählen Sie zuerst Ihr Nutzerprofil aus."
        if mgr and mgr.can_access_user(user) is not True:
            return "Dieser Google Kalender ist für Ihr Nutzerprofil nicht freigegeben."
        if not get_privacy_gate().allow(Capability.REMOTE_TOOL):
            return "Kalenderänderungen sind im aktuellen Datenschutzmodus gesperrt."
        if not mgr or not mgr.is_connected:
            return "Google Kalender benötigt die Freigabe durch den Eigentümer."
        if not mgr._jarvis_calendar_id:
            return "Ein vorhandener JARVIS Kalender wird benötigt. Es wurde nichts angelegt."
        if action not in ("create", "update", "delete"):
            return "Diese Kalenderaktion ist nicht verfügbar."
        if action != "create" and not payload.get("event_id"):
            return "Bitte wählen Sie einen eindeutigen Termin aus."
        if action in ("create", "update") and not payload.get("start_time"):
            return "Bitte nennen Sie eine gültige Uhrzeit."
        if action == "create" and not payload.get("title"):
            return "Bitte nennen Sie den Titel des Termins."
        detail = dict(payload, requester=user, calendar_id=mgr._jarvis_calendar_id)
        self._pending_confirmation = (action, detail, time.time() + 30)
        label = {"create": "anlegen", "update": "verschieben", "delete": "löschen"}[action]
        title = payload.get("title", "den gewählten Termin")
        when = payload.get("start_time")
        date = f" am {when:%d.%m.%Y} um {when:%H:%M} Uhr" if when else ""
        if action == "create":
            date += " für 15 Minuten"
        return f"Soll ich im JARVIS Kalender {title}{date} {label}? Bitte bestätigen Sie mit Ja oder Nein."

    def confirm_action(self, entities):
        pending = self._pending_confirmation
        if not pending:
            return "Keine Kalenderänderung wartet auf Bestätigung."
        action, detail, expiry = pending
        if time.time() > expiry or self._requester() != detail["requester"]:
            self._pending_confirmation = None
            return "Die Kalenderbestätigung ist abgelaufen oder das Nutzerprofil hat gewechselt."
        decision = parse_confirmation(entities.get("original_text", ""))
        if decision is None:
            return "Bitte bestätigen Sie die Kalenderänderung mit Ja oder Nein."
        self._pending_confirmation = None
        if not decision:
            return "Kalenderänderung abgebrochen."
        mgr = self.manager
        if (not mgr or not mgr.is_connected or mgr._jarvis_calendar_id != detail["calendar_id"]
                or mgr.can_access_user(self._requester()) is not True
                or not get_privacy_gate().allow(Capability.REMOTE_TOOL)):
            return "Der Kalender ist nicht verfügbar oder die Änderung ist gesperrt. Es wurde nichts geändert."
        try:
            if action == "create":
                result = mgr.create_event(detail["title"], detail["start_time"])
            elif action == "update":
                result = mgr.update_event(detail["event_id"], start_time=detail["start_time"])
            else:
                result = mgr.delete_event(detail["event_id"])
        except Exception:
            result = False
        return "Kalenderänderung gespeichert." if result else "Die Kalenderänderung konnte nicht gespeichert werden."

    def create_calendar_event(self):
        text = getattr(self, "_last_user_text", "")
        direct = re.fullmatch(
            r"trag(?:e)?\s+((?:heute|morgen)\s+um\s+\d{1,2}(?::\d{2})?\s*uhr)\s+(?:einen\s+)?(.+?)\s+ein[.!]?",
            text.strip(), re.I)
        if direct:
            return self.request_write("create", {"title": direct[2],
                                                 "start_time": ReminderManager.parse_natural_time(direct[1])})
        match = re.search(r"(?:termin)\s+(.+?)\s+(?:für|fuer)\s+(.+?)(?:\s+ein)?[.!]?$", text, re.I)
        if not match:
            return "Bitte sagen Sie: Erstelle einen Termin morgen um 17 Uhr für den Einkauf."
        return self.request_write("create", {"title": match[2],
                                             "start_time": ReminderManager.parse_natural_time(match[1])})

    def _find(self, title):
        if not self._requester():
            return []
        mgr = self.manager
        if not mgr or not mgr.is_connected or mgr.can_access_user(self._requester()) is not True:
            return []
        return mgr.find_dedicated_events(title)

    def delete_calendar_event(self):
        text = getattr(self, "_last_user_text", "")
        match = re.search(r"(?:termin)\s+(.+?)(?:\s+aus\s+dem\s+kalender)?[.!]?$", text, re.I)
        events = self._find(match[1]) if match else []
        if len(events) != 1:
            return "Bitte nennen Sie einen eindeutigen Termin im JARVIS Kalender."
        return self.request_write("delete", {"event_id": events[0]["google_event_id"], "title": events[0]["title"]})

    def update_calendar_event(self):
        text = getattr(self, "_last_user_text", "")
        match = re.search(r"termin\s+(.+?)\s+auf\s+(.+?)[.!]?$", text, re.I)
        events = self._find(match[1]) if match else []
        if len(events) != 1:
            return "Bitte nennen Sie einen eindeutigen Termin im JARVIS Kalender."
        return self.request_write("update", {"event_id": events[0]["google_event_id"], "title": events[0]["title"],
                                             "start_time": ReminderManager.parse_natural_time(match[2])})
