"""Tool definition: manage_reminders — reminder CRUD operations."""

from datetime import datetime
from core.privacy_gate import Capability, get_privacy_gate

TOOL_NAME = "manage_reminders"
SKILL_NAME = "reminders"

DEPENDENCIES = {
    "reminder_manager": "_reminder_manager",
    "current_user_fn": "_current_user_fn",
}

SCHEMA = {
    "type": "function",
    "function": {
        "name": "manage_reminders",
        "description": (
            "Manage reminders: set new ones, list existing, cancel, "
            "acknowledge, or snooze. Use for ANY request about reminders."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "cancel", "cancel_all", "acknowledge", "snooze"],
                    "description": (
                        "add: set a new reminder. "
                        "list: show upcoming reminders. "
                        "cancel: remove a reminder by name. "
                        "cancel_all: cancel ALL user-created reminders. "
                        "acknowledge: mark the last-fired reminder as done. "
                        "snooze: delay the last-fired reminder."
                    )
                },
                "title": {
                    "type": "string",
                    "description": (
                        "What to be reminded about (e.g. 'call mom', "
                        "'take out the trash'). Required for 'add'."
                    )
                },
                "time_text": {
                    "type": "string",
                    "description": (
                        "When to remind, in natural language "
                        "(e.g. 'tomorrow at 6 PM', 'in 30 minutes', "
                        "'next Tuesday'). Required for 'add'."
                    )
                },
                "priority": {
                    "type": "string",
                    "enum": ["urgent", "high", "normal"],
                    "description": (
                        "Importance level. Default: normal. "
                        "Urgent/high require acknowledgment when fired."
                    )
                },
                "snooze_minutes": {
                    "type": "integer",
                    "description": "Minutes to snooze. Default: 15."
                },
                "cancel_fragment": {
                    "type": "string",
                    "description": (
                        "Part of the reminder title to match for cancellation "
                        "(e.g. 'dentist'). Required for 'cancel'."
                    )
                }
            },
            "required": ["action"]
        }
    }
}

SYSTEM_PROMPT_RULE = (
    "For reminder requests (set, list, cancel, snooze, "
    "acknowledge), call manage_reminders. Extract the title and "
    "time from the user's words. "
    "Examples: 'remind me to call Mom at 3pm' → add with title='call Mom', time_text='3pm'. "
    "'set a reminder for 3pm to call the dentist' → add with title='call the dentist', time_text='3pm'. "
    "'remind me at 2pm to call mom' → add with title='call mom', time_text='2pm'. "
    "'what reminders do I have?' → list. "
    "'cancel the dentist reminder' → cancel with cancel_fragment='dentist'. "
    "'cancel all my reminders' → cancel_all. "
    "DISMISSING REMINDERS: If a reminder just fired (was spoken aloud) and the user says "
    "'cancel that', 'dismiss that', 'you can cancel that notification', 'stop reminding me', "
    "'never mind', or similar dismissive language → use action='acknowledge' (NOT cancel). "
    "Acknowledge means 'stop nagging, I heard it'. "
    "Only use action='cancel' with cancel_fragment when the user names a specific reminder "
    "unprompted (e.g. 'cancel the dentist reminder'). "
    "The title is WHAT to be reminded about. The time_text is WHEN. Both are required for add. "
    "EDITING A REMINDER: 'change X to Y' after setting a reminder = WORD SUBSTITUTION in the title. "
    "The user is replacing a word in the reminder title, nothing more. "
    "Example: title is 'call mom', user says 'change call to text' → cancel the old reminder, "
    "then add(title='text mom', time_text=<same time>). The new title is 'text mom'. "
    "This is NOT about sending SMS. Do NOT ask for phone numbers. Just swap the word and re-add. "
    "NOT for: calendar events, alarms, timers, scheduling meetings."
)


# ---------------------------------------------------------------------------
# Runtime dependencies — injected via tool_registry.inject_dependencies()
# ---------------------------------------------------------------------------

_reminder_manager = None
_current_user_fn = None  # Callable[[], str] — returns current user_id


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handler(args: dict) -> str:
    """Dispatch reminder actions to sub-handlers."""
    if not _reminder_manager:
        return "Das Erinnerungssystem ist nicht initialisiert."
    user = _current_user_fn() if _current_user_fn else None
    if not isinstance(user, str) or not user.strip() or user.casefold() in {"__guest__", "guest", "unknown", "anonymous", "none", "__unknown__"}:
        return "Bitte wählen Sie zuerst Ihr Nutzerprofil aus."

    action = args.get("action", "")
    if action != "list" and not get_privacy_gate().allow(Capability.MEMORY_WRITE):
        return "Erinnerungsänderungen sind im aktuellen Datenschutzmodus gesperrt."
    if action == "add":
        return _reminders_add(_reminder_manager, args)
    elif action == "list":
        return _reminders_list(_reminder_manager)
    elif action == "cancel":
        return _reminders_cancel(_reminder_manager, args)
    elif action == "cancel_all":
        return _reminders_cancel_all(_reminder_manager)
    elif action == "acknowledge":
        return _reminders_acknowledge(_reminder_manager)
    elif action == "snooze":
        return _reminders_snooze(_reminder_manager, args)
    else:
        return f"Unbekannte Erinnerungsaktion: '{action}'."


# ---------------------------------------------------------------------------
# Sub-handlers
# ---------------------------------------------------------------------------

def _reminders_add(mgr, args: dict) -> str:
    """Add a new one-time reminder."""
    title = args.get("title", "").strip()
    time_text = args.get("time_text", "").strip()

    if not title:
        return "Bitte gib einen Titel für die Erinnerung an."
    if not time_text:
        return "Bitte gib einen Zeitpunkt an, zum Beispiel morgen um 18 Uhr."

    priority_str = args.get("priority", "normal").lower()
    priority_map = {"urgent": 1, "high": 2, "normal": 3}
    priority = priority_map.get(priority_str, 3)

    # Use the manager's existing natural-time parser
    from core.reminder_manager import ReminderManager
    reminder_time = ReminderManager.parse_natural_time(time_text)
    if not reminder_time:
        return (f"Ich konnte den Zeitpunkt '{time_text}' nicht erkennen. "
                "Versuche zum Beispiel morgen um 18 Uhr oder in 30 Minuten.")

    created_by = _current_user_fn()
    rid = mgr.add_reminder(
        title=title,
        reminder_time=reminder_time,
        priority=priority,
        created_by=created_by,
        origin_endpoint='voice',
    )

    time_desc = _format_reminder_time(reminder_time)
    priority_note = " (dringend)" if priority <= 2 else ""
    return f"Erinnerung #{rid} eingerichtet: '{title}' {time_desc}{priority_note}."


def _reminders_list(mgr) -> str:
    """List upcoming and fired reminders."""
    created_by = _current_user_fn()
    pending = mgr.list_reminders("pending", limit=50, created_by=created_by)
    fired = mgr.list_reminders("fired", limit=5, created_by=created_by)
    all_reminders = fired + pending

    if not all_reminders:
        return "Es stehen keine Erinnerungen an."

    lines = []
    for r in all_reminders:
        try:
            rt = datetime.strptime(r["reminder_time"], "%Y-%m-%d %H:%M:%S")
            time_desc = _format_reminder_time(rt)
        except (ValueError, KeyError):
            time_desc = r.get("reminder_time", "unbekannter Zeitpunkt")
        status_note = " [wartet auf Bestätigung]" if r["status"] == "fired" else ""
        lines.append(f"- {r['title']}{status_note}, {time_desc}")

    count = len(all_reminders)
    header = f"{count} Erinnerungen:"
    return header + "\n" + "\n".join(lines)


def _reminders_cancel_all(mgr) -> str:
    """Cancel all user-created pending/fired reminders (not Google Calendar synced)."""
    created_by = _current_user_fn()
    pending = mgr.list_reminders("pending", limit=500, created_by=created_by)
    pending.extend(mgr.list_reminders("fired", limit=500, created_by=created_by))
    # Only cancel reminders the user created, not Google Calendar synced ones
    user_reminders = [r for r in pending if r.get("origin_endpoint") != "google_calendar"]
    if not user_reminders:
        return "Es gibt keine selbst angelegten Erinnerungen zum Abbrechen."
    for r in user_reminders:
        mgr.cancel_reminder(r["id"])
    return f"{len(user_reminders)} Erinnerungen abgebrochen."


def _reminders_cancel(mgr, args: dict) -> str:
    """Cancel a reminder by title fragment."""
    fragment = args.get("cancel_fragment", "").strip()
    if not fragment:
        return "Bitte gib an, welche Erinnerung abgebrochen werden soll, zum Beispiel Zahnarzt."

    created_by = _current_user_fn()
    cancelled = mgr.cancel_by_title(fragment, created_by=created_by)
    if cancelled:
        return f"Abgebrochen: '{cancelled['title']}'."
    return f"Keine passende Erinnerung für '{fragment}' gefunden."


def _reminders_acknowledge(mgr) -> str:
    """Acknowledge the last-fired reminder."""
    user = _current_user_fn() if _current_user_fn else None
    if not user:
        return "Bitte wählen Sie zuerst Ihr Nutzerprofil aus."
    if not mgr.is_awaiting_ack(created_by=user):
        return "Keine Erinnerung wartet auf Bestätigung."

    reminder = mgr.acknowledge_last(created_by=user)
    if reminder:
        return f"Bestätigt: '{reminder['title']}' als erledigt markiert."
    return "Die Erinnerung konnte nicht bestätigt werden."


def _reminders_snooze(mgr, args: dict) -> str:
    """Snooze the last-fired reminder."""
    user = _current_user_fn() if _current_user_fn else None
    if not user:
        return "Bitte wählen Sie zuerst Ihr Nutzerprofil aus."
    if not mgr.is_awaiting_ack(created_by=user):
        return "Zurzeit gibt es keine Erinnerung zum Verschieben."

    minutes = args.get("snooze_minutes")
    reminder = mgr.snooze_last(minutes, created_by=user)
    if reminder:
        snooze_min = minutes or mgr.default_snooze
        return f"'{reminder['title']}' um {snooze_min} Minuten verschoben."
    return "Die Erinnerung konnte nicht verschoben werden."


def _format_reminder_time(dt) -> str:
    """Format a reminder datetime for LLM context (relative when possible)."""
    now = datetime.now()
    diff = dt - now

    total_seconds = diff.total_seconds()
    if total_seconds < 0:
        return f"um {dt.strftime('%H:%M')} Uhr (bereits vergangen)"
    elif total_seconds < 90:
        return "in etwa einer Minute"
    elif total_seconds < 3600:
        minutes = int(total_seconds / 60)
        return f"in {minutes} Minuten"
    elif total_seconds < 7200:
        return "in etwa einer Stunde"

    if dt.date() == now.date():
        return f"heute um {dt.strftime('%H:%M')} Uhr"
    elif (dt.date() - now.date()).days == 1:
        return f"morgen um {dt.strftime('%H:%M')} Uhr"
    elif (dt.date() - now.date()).days < 7:
        return f"am {dt.strftime('%d.%m.')} um {dt.strftime('%H:%M')} Uhr"
    else:
        return f"am {dt.strftime('%d.%m.%Y')} um {dt.strftime('%H:%M')} Uhr"
