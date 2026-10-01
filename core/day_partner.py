"""Deterministic, read-only calendar and reminder overview for the active user."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


class DayPartner:
    def __init__(self, reminder_manager, calendar_manager=None, timezone="Europe/Berlin"):
        self.reminders = reminder_manager
        self.calendar = calendar_manager
        self.timezone = ZoneInfo(timezone)

    def get_overview(self, period="today", planning=False, created_by=None, now=None, sources="all"):
        if (not isinstance(created_by, str) or not created_by.strip()
                or created_by.casefold() in {"__guest__", "guest", "unknown", "anonymous", "none", "__unknown__"}):
            return "Bitte wählen Sie zuerst Ihr Nutzerprofil aus."
        if period not in ("today", "tomorrow", "week"):
            return "Bitte nennen Sie heute, morgen oder diese Woche."
        if sources not in ("all", "reminders", "calendar"):
            return "Diese Datenquelle ist nicht verfügbar."
        calendar_allowed = bool(sources != "reminders" and self.calendar
                                and self.calendar.can_access_user(created_by) is True)
        configured_calendar_zone = getattr(self.calendar, "_primary_timezone", None) if calendar_allowed else None
        display_zone = ZoneInfo(configured_calendar_zone) if isinstance(configured_calendar_zone, str) else self.timezone
        current = now or datetime.now(display_zone)
        current = (current.replace(tzinfo=display_zone) if current.tzinfo is None
                   else current.astimezone(display_zone)).replace(tzinfo=None)
        start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "tomorrow":
            start += timedelta(days=1)
        elif period == "week":
            start -= timedelta(days=start.weekday())
        end = start + timedelta(days=7 if period == "week" else 1)
        label = {"today": "Heute", "tomorrow": "Morgen", "week": "Diese Woche"}[period]
        items, messages = [], []
        def local_time(value):
            return value.astimezone(display_zone).replace(tzinfo=None) if value.tzinfo else value
        outcome = None
        represented_ids = set()
        if self.calendar and sources != "reminders":
            try:
                if calendar_allowed:
                    outcome = self.calendar.read_events(period, now=current)
            except Exception:
                pass
        if sources == "reminders":
            pass
        elif self.calendar and not calendar_allowed:
            messages.append("Dieser Google Kalender ist für Ihr Nutzerprofil nicht freigegeben.")
        elif outcome is None or not outcome.available:
            messages.append("Google Kalender ist derzeit nicht verfügbar; Ihre Termine kann ich nicht prüfen.")
        else:
            calendar_zone = getattr(self.calendar, "_primary_timezone", None)
            calendar_zone = ZoneInfo(calendar_zone) if isinstance(calendar_zone, str) else self.timezone
            def calendar_time(value):
                return local_time(value if value.tzinfo else value.replace(tzinfo=calendar_zone))
            for event in outcome.events:
                if event.get("google_event_id"):
                    represented_ids.add(event["google_event_id"])
                items.append(dict(start=calendar_time(event["start_time"]), end=calendar_time(event.get("end_time", event["start_time"])),
                                  title=event["title"], calendar=True, all_day=event.get("all_day", False)))
        if self.reminders and sources != "calendar":
            try:
                start_db = start.replace(tzinfo=display_zone).astimezone(self.timezone).strftime("%Y-%m-%d %H:%M:%S")
                end_db = end.replace(tzinfo=display_zone).astimezone(self.timezone)
                if sources == "reminders":
                    rows = self.reminders.list_range(start_db, end_db.strftime("%Y-%m-%d %H:%M:%S"), created_by=created_by)
                else:
                    rows = self.reminders._query_rundown_reminders(
                        start_db, (end_db - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S"), created_by=created_by)
                for row in rows:
                    # Retain local sync copies unless the remote event is actually represented.
                    gid = row.get("google_event_id")
                    if gid:
                        if self.calendar:
                            copy_allowed = self.calendar.can_access_user(created_by) is True
                        else:
                            config = getattr(self.reminders, "config", None)
                            owner = config.get("user_profiles.primary_user_id", "primary_user") if config else None
                            copy_allowed = isinstance(owner, str) and owner == created_by
                        if not copy_allowed:
                            continue
                    if gid and gid.split(":")[0] in represented_ids:
                        continue
                    is_calendar_copy = bool(gid and row.get("event_time") and sources != "reminders")
                    dt = datetime.fromisoformat(row["event_time"] if is_calendar_copy else row["reminder_time"])
                    dt = local_time(dt if dt.tzinfo else dt.replace(tzinfo=self.timezone))
                    items.append(dict(start=dt, end=dt, title=row["title"], calendar=is_calendar_copy, all_day=False))
            except Exception:
                messages.append("Die Erinnerungen sind derzeit nicht verfügbar.")
        elif sources != "calendar":
            messages.append("Die Erinnerungen sind derzeit nicht verfügbar.")
        items.sort(key=lambda item: item["start"])
        if items:
            entries = []
            for item in items:
                when = "ganztägig" if item["all_day"] else item["start"].strftime("%H:%M Uhr")
                if period == "week":
                    when = item["start"].strftime("%d.%m. ") + when
                kind = "Termin" if item["calendar"] else "Erinnerung"
                entries.append(f"{kind} {when}: {item['title']}")
            messages.append(f"{label}: " + "; ".join(entries) + ".")
        else:
            messages.append(f"{label} liegen mir keine verfügbaren Einträge vor.")
        overlaps = []
        for index, item in enumerate(items):
            if not item["calendar"] or item["all_day"]:
                continue
            for other in items[index + 1:]:
                if other["start"] >= item["end"]:
                    break
                if not other["all_day"]:
                    overlaps.append(f"{item['title']} und {other['title']}")
        if overlaps:
            messages.append("Zeitliche Überschneidung: " + "; ".join(overlaps) + ".")
        upcoming = [item for item in items if item["start"] >= current]
        if upcoming:
            messages.append("Als Nächstes: " + upcoming[0]["title"] + ".")
        if planning:
            if outcome is None or not outcome.available:
                messages.append("Ohne Kalenderdaten kann ich freie Zeitblöcke nicht sicher planen.")
            elif any(item["all_day"] for item in items):
                messages.append("Ganztägige Termine sind vermerkt; ihre zeitliche Bindung muss geklärt werden.")
            else:
                cursor = max(start.replace(hour=8), current) if period == "today" else start.replace(hour=8)
                finish = start.replace(hour=20)
                blocks = []
                for item in items:
                    if item["start"] > cursor + timedelta(minutes=29):
                        block_end = min(item["start"], finish)
                        if block_end - cursor >= timedelta(minutes=30):
                            blocks.append(f"{cursor:%H:%M} bis {block_end:%H:%M} Uhr")
                    cursor = max(cursor, item["end"] + timedelta(minutes=15))
                if finish - cursor >= timedelta(minutes=30):
                    blocks.append(f"{cursor:%H:%M} bis {finish:%H:%M} Uhr")
                messages.append("Vorschlag für freie Blöcke mit 15 Minuten Puffer: " +
                                (", ".join(blocks) if blocks else "keine ausreichend langen Blöcke") + ".")
            messages.append("Dies ist ein Vorschlag. Es wurde kein Termin und keine Erinnerung geändert.")
        return " ".join(messages)
