"""
Google Calendar Manager

Handles OAuth2 authentication, event CRUD, and two-way sync between
JARVIS's local reminder database and Google Calendar.

Uses a dedicated "JARVIS" secondary calendar for voice-created reminders.
Primary calendar events are read for daily rundown but not auto-imported
as local reminders.

Singleton pattern — access via get_calendar_manager().
"""

import json
import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo


@dataclass
class CalendarReadOutcome:
    status: str
    events: list = field(default_factory=list)

    @property
    def available(self):
        return self.status == "success"

from core.logger import get_logger
from core.privacy_gate import Capability, get_privacy_gate

# Singleton instance
_instance: Optional["GoogleCalendarManager"] = None


def get_calendar_manager(config=None) -> Optional["GoogleCalendarManager"]:
    """Get or create the singleton GoogleCalendarManager.

    Call with config on first invocation (from jarvis_continuous.py).
    Call with no args from other modules to retrieve the existing instance.
    """
    global _instance
    if _instance is None and config is not None:
        _instance = GoogleCalendarManager(config)
    return _instance


class GoogleCalendarManager:
    """Handles OAuth, event CRUD, and background sync with Google Calendar."""

    # Google Calendar API scopes
    SCOPES = ["https://www.googleapis.com/auth/calendar"]

    def can_access_user(self, user_id):
        """The existing configured primary identity owns this global OAuth token."""
        owner = self.config.get("user_profiles.primary_user_id", "primary_user")
        return isinstance(owner, str) and bool(owner.strip()) and isinstance(user_id, str) and user_id == owner

    def __init__(self, config):
        self.config = config
        self.logger = get_logger(__name__, config)

        # Paths
        self._credentials_path = os.path.expanduser(
            config.get("google_calendar.credentials_path", "~/jarvis/credentials.json")
        )
        self._token_path = os.path.expanduser(
            config.get("google_calendar.token_path",
                        "/home/alex/jarvis-data/data/google_token.json")
        )
        self._sync_token_path = os.path.expanduser(
            config.get("google_calendar.sync_token_path",
                        "/home/alex/jarvis-data/data/google_sync_token.json")
        )

        # Config
        self._sync_interval = config.get("google_calendar.sync_interval_seconds", 300)
        self._calendar_name = config.get("google_calendar.jarvis_calendar_name", "JARVIS")
        self._include_primary = config.get("google_calendar.include_primary_in_rundown", True)
        self._timezone = config.get("google_calendar.timezone", "Europe/Berlin")
        self.auth_status = "GOOGLE_AUTH_BLOCKED_PENDING_OWNER"
        self._primary_timezone = self._timezone
        self.timezone_verified = False

        # State
        self.creds = None
        self.service = None
        self._jarvis_calendar_id = None
        self._sync_token = None
        self._running = False
        self._thread = None

        # Callback for creating local reminders from Google events
        self._on_new_event: Optional[Callable] = None
        self._on_cancel_event: Optional[Callable] = None

        # Authenticate
        self._authenticated = False
        try:
            self._authenticate()
            self._authenticated = True
            self.auth_status = "ready"
            self._load_sync_token()
            self._ensure_jarvis_calendar()
            self.logger.info("Google Calendar authenticated and ready")
        except FileNotFoundError:
            self.logger.warning(
                f"Google Calendar credentials not found at {self._credentials_path}. "
                "Calendar sync disabled. Download credentials.json from Google Cloud Console."
            )
        except Exception as e:
            self.logger.error("Google Calendar auth failed (%s)", type(e).__name__)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _authenticate(self):
        """Reuse existing scopes and token; interactive authorization requires owner."""
        get_privacy_gate().assert_allowed(Capability.REMOTE_TOOL)
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = None
        if os.path.exists(self._token_path):
            creds = Credentials.from_authorized_user_file(self._token_path)
            if not (creds.has_scopes(self.SCOPES) or creds.has_scopes(
                    ["https://www.googleapis.com/auth/calendar.readonly"])):
                raise PermissionError("Existing Calendar token scope is insufficient")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self.logger.info("Refreshing Google Calendar token...")
                creds.refresh(Request())
            else:
                raise PermissionError("Calendar authorization requires owner")

            # Persist token
            os.makedirs(os.path.dirname(self._token_path), exist_ok=True)
            with open(self._token_path, "w") as f:
                f.write(creds.to_json())

        self.creds = creds
        self._build_service()

    def _build_service(self):
        """Build the Google Calendar API service object."""
        from googleapiclient.discovery import build

        self.service = build("calendar", "v3", credentials=self.creds)

    def _ensure_valid(self):
        """Refresh access token if expired. Persist refreshed token."""
        if not get_privacy_gate().allow(Capability.REMOTE_TOOL):
            return False
        if not self._authenticated or not self.creds:
            return False

        from google.auth.transport.requests import Request
        from google.auth.exceptions import RefreshError

        if self.creds.expired:
            try:
                self.creds.refresh(Request())
                with open(self._token_path, "w") as f:
                    f.write(self.creds.to_json())
                self._build_service()
                return True
            except RefreshError:
                self.logger.error(
                    "Google Calendar token revoked! Re-authorization required. "
                    "Delete token.json and restart JARVIS."
                )
                self._authenticated = False
                return False
        return True

    # ------------------------------------------------------------------
    # Calendar Management
    # ------------------------------------------------------------------

    def _ensure_jarvis_calendar(self):
        """Find or create the dedicated JARVIS secondary calendar."""
        if not self._authenticated:
            return

        try:
            # Metadata only: honor the actual Google timezone when available.
            candidates = []
            token = None
            while True:
                params = {"pageToken": token} if token else {}
                calendar_list = self.service.calendarList().list(**params).execute()
                for cal in calendar_list.get("items", []):
                    zone = cal.get("timeZone")
                    if zone:
                        ZoneInfo(zone)  # Validate IANA timezone before adopting it.
                    if cal.get("primary") and zone:
                        self._primary_timezone = zone
                        self.timezone_verified = True
                    if cal.get("summary") == self._calendar_name and not cal.get("primary"):
                        candidates.append(cal)
                token = calendar_list.get("nextPageToken")
                if not token:
                    break
            if len(candidates) == 1:
                cal = candidates[0]
                self._jarvis_calendar_id = cal["id"]
                if cal.get("timeZone"):
                    self._timezone = cal["timeZone"]
                self.logger.info("Existing dedicated Calendar selected")
            else:
                self.logger.warning("Dedicated Calendar absent or ambiguous; owner setup required")

        except Exception as e:
            self.logger.error("Calendar operation: content suppressed")

    # ------------------------------------------------------------------
    # Event CRUD
    # ------------------------------------------------------------------

    def create_event(self, title: str, start_time: datetime,
                     priority: int = 3, description: str = "") -> Optional[str]:
        """Create an event on the JARVIS calendar.

        Returns the Google event ID, or None on failure.
        """
        if not self._authenticated or not self._jarvis_calendar_id:
            return None
        if not self.creds or not self.creds.has_scopes(self.SCOPES):
            return None

        if not self._ensure_valid():
            return None

        # Build reminder overrides based on priority
        if priority <= 2:
            reminders = {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                    {"method": "popup", "minutes": 10},
                    {"method": "popup", "minutes": 0},
                ],
            }
        else:
            reminders = {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 10},
                ],
            }

        # Events need an end time — use 15 min duration for reminders
        end_time = start_time + timedelta(minutes=15)

        priority_label = {1: "[URGENT] ", 2: "[IMPORTANT] ", 3: "", 4: "[low] "}
        event_body = {
            "summary": f"{priority_label.get(priority, '')}{title}",
            "description": description or f"JARVIS reminder (priority {priority})",
            "start": {
                "dateTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": self._timezone,
            },
            "end": {
                "dateTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": self._timezone,
            },
            "reminders": reminders,
        }

        try:
            created = self.service.events().insert(
                calendarId=self._jarvis_calendar_id,
                body=event_body,
            ).execute()
            event_id = created["id"]
            self.logger.info("Calendar operation: content suppressed")
            return event_id
        except Exception as e:
            self.logger.error("Calendar operation: content suppressed")
            return None

    def update_event(self, event_id: str, **kwargs) -> bool:
        """Update an existing event (title, start_time, description)."""
        if not self._authenticated or not self._jarvis_calendar_id or not event_id:
            return False
        if not self.creds or not self.creds.has_scopes(self.SCOPES):
            return False

        if not self._ensure_valid():
            return False

        try:
            # Fetch current event
            event = self.service.events().get(
                calendarId=self._jarvis_calendar_id,
                eventId=event_id,
            ).execute()

            # Apply updates
            if "title" in kwargs:
                event["summary"] = kwargs["title"]
            if "start_time" in kwargs:
                start = kwargs["start_time"]
                old_start = datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00"))
                old_end = datetime.fromisoformat(event["end"]["dateTime"].replace("Z", "+00:00"))
                duration = old_end - old_start
                if duration <= timedelta(0):
                    return False
                end = start + duration
                event["start"]["dateTime"] = start.strftime("%Y-%m-%dT%H:%M:%S")
                event["end"]["dateTime"] = end.strftime("%Y-%m-%dT%H:%M:%S")
                event["start"]["timeZone"] = self._timezone
                event["end"]["timeZone"] = self._timezone
            if "description" in kwargs:
                event["description"] = kwargs["description"]

            self.service.events().update(
                calendarId=self._jarvis_calendar_id,
                eventId=event_id,
                body=event,
            ).execute()
            self.logger.info("Calendar operation: content suppressed")
            return True
        except Exception as e:
            self.logger.error("Calendar operation: content suppressed")
            return False

    def delete_event(self, event_id: str) -> bool:
        """Delete an event from the JARVIS calendar."""
        if not self._authenticated or not self._jarvis_calendar_id or not event_id:
            return False
        if not self.creds or not self.creds.has_scopes(self.SCOPES):
            return False

        if not self._ensure_valid():
            return False

        try:
            self.service.events().delete(
                calendarId=self._jarvis_calendar_id,
                eventId=event_id,
            ).execute()
            self.logger.info("Calendar operation: content suppressed")
            return True
        except Exception as e:
            self.logger.error("Calendar operation: content suppressed")
            return False

    # ------------------------------------------------------------------
    # Sync: Google → JARVIS
    # ------------------------------------------------------------------

    def sync_from_google(self) -> Dict[str, List[Dict]]:
        """Pull new/modified/deleted events from the JARVIS calendar.

        Uses incremental syncToken for efficiency.

        Returns dict with keys: 'new', 'updated', 'deleted'
        Each value is a list of event dicts.
        """
        if not self._authenticated or not self._jarvis_calendar_id:
            return {"new": [], "updated": [], "deleted": []}

        if not self._ensure_valid():
            return {"new": [], "updated": [], "deleted": []}

        result = {"new": [], "updated": [], "deleted": []}

        try:
            kwargs = {"calendarId": self._jarvis_calendar_id, "singleEvents": True}

            if self._sync_token:
                kwargs["syncToken"] = self._sync_token
            else:
                # First sync: get events from today forward
                # NOTE: Do NOT use orderBy here — it prevents Google from
                # returning a nextSyncToken, breaking incremental sync.
                now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + self._tz_offset()
                kwargs["timeMin"] = now

            page_token = None
            while True:
                if page_token:
                    kwargs["pageToken"] = page_token

                events_result = self.service.events().list(**kwargs).execute()

                for event in events_result.get("items", []):
                    status = event.get("status", "confirmed")
                    event_id = event["id"]

                    if status == "cancelled":
                        result["deleted"].append({"google_event_id": event_id})
                    else:
                        parsed = self._parse_google_event(event)
                        if parsed:
                            parsed["google_event_id"] = event_id
                            result["new"].append(parsed)

                # nextSyncToken only appears on the final page
                new_token = events_result.get("nextSyncToken")
                if new_token:
                    self._sync_token = new_token
                    self._save_sync_token()
                    break

                # Follow pagination to get all pages
                page_token = events_result.get("nextPageToken")
                if not page_token:
                    break

            if result["new"] or result["deleted"]:
                self.logger.info(
                    f"Google sync: {len(result['new'])} new/updated, "
                    f"{len(result['deleted'])} deleted"
                )

        except Exception as e:
            err_str = str(e)
            if "410" in err_str or "fullSyncRequired" in err_str:
                # Sync token expired — do a full re-sync
                self.logger.warning("Sync token expired, performing full sync")
                self._sync_token = None
                self._save_sync_token()
                return self.sync_from_google()
            self.logger.error("Calendar operation: content suppressed")

        return result

    def read_events(self, period="today", now=None) -> CalendarReadOutcome:
        """Read complete local calendar ranges without treating failures as empty days."""
        if period not in ("today", "tomorrow", "week"):
            return CalendarReadOutcome("invalid_period")
        if not get_privacy_gate().allow(Capability.REMOTE_TOOL):
            return CalendarReadOutcome("privacy_blocked")
        if not self._authenticated:
            return CalendarReadOutcome("auth_blocked")
        if not self._include_primary and not self._jarvis_calendar_id:
            return CalendarReadOutcome("disabled")
        try:
            if not self._ensure_valid():
                return CalendarReadOutcome("auth_blocked")
            tz = ZoneInfo(getattr(self, "_primary_timezone", self._timezone))
            current = now or datetime.now(tz)
            current = current.replace(tzinfo=tz) if current.tzinfo is None else current.astimezone(tz)
            start = current.replace(hour=0, minute=0, second=0, microsecond=0)
            if period == "tomorrow":
                start += timedelta(days=1)
            elif period == "week":
                start -= timedelta(days=start.weekday())
            end = start + timedelta(days=7 if period == "week" else 1)
            results = []
            calendar_ids = (["primary"] if self._include_primary else [])
            if self._jarvis_calendar_id and self._jarvis_calendar_id not in calendar_ids:
                calendar_ids.append(self._jarvis_calendar_id)
            seen_ids = set()
            for calendar_id in calendar_ids:
                token = None
                while True:
                    params = dict(calendarId=calendar_id, timeMin=start.isoformat(),
                              timeMax=end.isoformat(), singleEvents=True,
                              orderBy="startTime", maxResults=2500)
                    if token:
                        params["pageToken"] = token
                    response = self.service.events().list(**params).execute()
                    for event in response.get("items", []):
                        if event.get("status") == "cancelled":
                            continue
                        event_id = event.get("id")
                        if event_id and event_id in seen_ids:
                            continue
                        parsed = self._parse_google_event(event, timezone=getattr(self, "_primary_timezone", self._timezone))
                        if parsed:
                            if event_id:
                                seen_ids.add(event_id)
                            results.append(parsed)
                    token = response.get("nextPageToken")
                    if not token:
                        break
            results.sort(key=lambda event: event["start_time"])
            return CalendarReadOutcome("success", results)
        except Exception as exc:
            self.logger.warning("Calendar read failed (%s)", type(exc).__name__)
            return CalendarReadOutcome("unavailable")

    def find_dedicated_events(self, title):
        """Exact title selection; multiple identical names require clarification."""
        if not self._jarvis_calendar_id or not self._ensure_valid():
            return []
        try:
            items, token = [], None
            while True:
                args = dict(calendarId=self._jarvis_calendar_id, singleEvents=True,
                            maxResults=2500, timeMin=datetime.now(ZoneInfo(self._timezone)).isoformat())
                if token:
                    args["pageToken"] = token
                response = self.service.events().list(**args).execute()
                for event in response.get("items", []):
                    parsed = self._parse_google_event(event)
                    if parsed and event.get("status") != "cancelled" and parsed["title"].casefold() == title.strip().casefold():
                        items.append(parsed)
                token = response.get("nextPageToken")
                if not token:
                    return items
        except Exception as exc:
            self.logger.warning("Calendar selection failed (%s)", type(exc).__name__)
            return []

    def get_primary_events_today(self):
        return self.read_events("today").events

    def get_primary_events_tomorrow(self):
        return self.read_events("tomorrow").events

    def get_primary_events_week(self):
        return self.read_events("week").events

    def get_upcoming_context(self, hours: int = 4) -> List[Dict]:
        """Get upcoming events for awareness injection.

        Returns lightweight event data for the next N hours.
        Cached for 5 minutes to avoid API spam.
        """
        if (not self._authenticated or not self._include_primary
                or not get_privacy_gate().allow(Capability.REMOTE_TOOL)):
            return []

        # Simple TTL cache
        now = time.time()
        cache_key = "_upcoming_context_cache"
        cache_ts_key = "_upcoming_context_ts"
        cached = getattr(self, cache_key, None)
        cached_ts = getattr(self, cache_ts_key, 0)
        if cached is not None and (now - cached_ts) < 300:  # 5-minute TTL
            return cached

        if not self._ensure_valid():
            return []

        try:
            now_dt = datetime.now(ZoneInfo(self._timezone))
            end_dt = now_dt + timedelta(hours=hours)

            tz = self._tz_offset()

            # Query both primary and JARVIS calendars
            calendar_ids = ["primary"]
            if self._jarvis_calendar_id:
                calendar_ids.append(self._jarvis_calendar_id)

            seen_ids = set()  # Dedup across calendars
            results = []

            for cal_id in calendar_ids:
                try:
                    events_result = self.service.events().list(
                        calendarId=cal_id,
                        timeMin=now_dt.isoformat(),
                        timeMax=end_dt.isoformat(),
                        singleEvents=True,
                        orderBy="startTime",
                        maxResults=10,
                    ).execute()
                except Exception as e:
                    self.logger.warning("Calendar operation: content suppressed")
                    continue

                for event in events_result.get("items", []):
                    eid = event.get("id", "")
                    if eid in seen_ids:
                        continue
                    seen_ids.add(eid)

                    parsed = self._parse_google_event(event)
                    if parsed:
                        # Detect all-day events (Google uses "date" not "dateTime")
                        start_raw = event.get("start", {})
                        is_all_day = "date" in start_raw and "dateTime" not in start_raw

                        delta = parsed["start_time"] - now_dt.replace(tzinfo=None)
                        minutes_until = max(0, int(delta.total_seconds() / 60))
                        # Extract attendees if available
                        attendees = [
                            a.get("displayName") or a.get("email", "")
                            for a in event.get("attendees", [])
                            if not a.get("self")
                        ]
                        results.append({
                            "title": parsed["title"],
                            "start_time": parsed["start_time"],
                            "minutes_until": minutes_until,
                            "attendees": attendees,
                            "all_day": is_all_day,
                        })

            # Sort merged results by start time
            results.sort(key=lambda e: e["start_time"])

            setattr(self, cache_key, results)
            setattr(self, cache_ts_key, now)
            return results

        except Exception as e:
            self.logger.error("Calendar operation: content suppressed")
            return []

    def _parse_google_event(self, event: Dict, timezone=None) -> Optional[Dict]:
        """Parse a Google Calendar event into a JARVIS-friendly dict."""
        summary = event.get("summary") or "Termin ohne Titel"

        # Extract priority from title prefix
        priority = 3
        clean_title = summary
        if summary.startswith("[URGENT] "):
            priority = 1
            clean_title = summary[9:]
        elif summary.startswith("[IMPORTANT] "):
            priority = 2
            clean_title = summary[12:]
        elif summary.startswith("[low] "):
            priority = 4
            clean_title = summary[6:]

        # Parse start time
        start = event.get("start", {})
        start_str = start.get("dateTime") or start.get("date")
        if not start_str:
            return None

        try:
            # Handle ISO format with timezone offset
            tz = ZoneInfo(timezone or self._timezone)
            start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            if start_time.tzinfo is not None:
                start_time = start_time.astimezone(tz).replace(tzinfo=None)
            end_raw = event.get("end", {})
            end_str = end_raw.get("dateTime") or end_raw.get("date")
            end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00")) if end_str else start_time
            if end_time.tzinfo is not None:
                end_time = end_time.astimezone(tz).replace(tzinfo=None)
        except ValueError:
            return None

        # Extract ALL reminder offsets (minutes before event)
        # Google API: reminders.overrides = [{"method": "popup", "minutes": 15}, ...]
        # Each offset becomes a separate JARVIS reminder so all notifications fire.
        reminder_minutes_list = []
        reminders_data = event.get("reminders", {})
        if reminders_data.get("useDefault"):
            reminder_minutes_list = [15]
        else:
            overrides = reminders_data.get("overrides", [])
            reminder_minutes_list = sorted(set(
                r["minutes"] for r in overrides
                if r.get("method") in ("popup", "email") and "minutes" in r
            ), reverse=True)  # largest offset first (earliest notification)

        return {
            "title": clean_title,
            "start_time": start_time,
            "end_time": end_time,
            "all_day": "dateTime" not in start,
            "priority": priority,
            "description": event.get("description", ""),
            "google_event_id": event.get("id"),
            "reminder_minutes_list": reminder_minutes_list,
        }

    def _tz_offset(self) -> str:
        """Get the local timezone offset string (e.g., '-06:00')."""
        now = datetime.now()
        utc_now = datetime.utcnow()
        diff = now - utc_now
        total_seconds = int(diff.total_seconds())
        hours = total_seconds // 3600
        minutes = abs(total_seconds) % 3600 // 60
        return f"{hours:+03d}:{minutes:02d}"

    # ------------------------------------------------------------------
    # Sync Token Persistence
    # ------------------------------------------------------------------

    def _load_sync_token(self):
        """Load sync token from disk."""
        if os.path.exists(self._sync_token_path):
            try:
                with open(self._sync_token_path) as f:
                    data = json.load(f)
                    self._sync_token = data.get("sync_token")
                    self.logger.info("Loaded Google Calendar sync token")
            except Exception:
                self._sync_token = None

    def _save_sync_token(self):
        """Persist sync token to disk."""
        try:
            os.makedirs(os.path.dirname(self._sync_token_path), exist_ok=True)
            with open(self._sync_token_path, "w") as f:
                json.dump({"sync_token": self._sync_token}, f)
        except Exception as e:
            self.logger.error("Calendar operation: content suppressed")

    # ------------------------------------------------------------------
    # Background Sync Thread
    # ------------------------------------------------------------------

    def set_sync_callbacks(self, on_new_event: Callable, on_cancel_event: Callable):
        """Set callbacks for when events are synced from Google.

        on_new_event(title, start_time, priority, google_event_id, reminder_minutes) -> int
        on_cancel_event(google_event_id) -> bool
        """
        self._on_new_event = on_new_event
        self._on_cancel_event = on_cancel_event

    def start(self):
        """Start the background sync thread."""
        if not self._authenticated:
            self.logger.warning("Google Calendar not authenticated — sync disabled")
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        self.logger.info(f"Google Calendar sync started (interval={self._sync_interval}s)")

    def stop(self):
        """Stop the background sync thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        self.logger.info("Google Calendar sync stopped")

    def _poll_loop(self):
        """Background thread: sync from Google periodically."""
        while self._running:
            try:
                changes = self.sync_from_google()

                # Process new events from JARVIS calendar → create local reminders
                # Each event may have multiple reminder offsets (e.g., 1 week + 30 min),
                # so call the callback once per offset to create separate reminders.
                if self._on_new_event:
                    for event in changes["new"]:
                        offsets = event.get("reminder_minutes_list", [])
                        if not offsets:
                            # No explicit reminders — create one at event time
                            self._on_new_event(
                                title=event["title"],
                                start_time=event["start_time"],
                                priority=event["priority"],
                                google_event_id=event["google_event_id"],
                                reminder_minutes=None,
                            )
                        else:
                            for offset in offsets:
                                self._on_new_event(
                                    title=event["title"],
                                    start_time=event["start_time"],
                                    priority=event["priority"],
                                    google_event_id=event["google_event_id"],
                                    reminder_minutes=offset,
                                )

                # Process deleted events → cancel local reminders
                if self._on_cancel_event:
                    for event in changes["deleted"]:
                        self._on_cancel_event(event["google_event_id"])

            except Exception as e:
                self.logger.error("Calendar operation: content suppressed")

            # Sleep in small increments for responsive shutdown
            for _ in range(self._sync_interval):
                if not self._running:
                    return
                time.sleep(1)

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    def check_connection(self) -> bool:
        """Verify Google Calendar connection is active."""
        if not self._authenticated:
            return False

        if not self._ensure_valid():
            return False
        try:
            self.service.calendarList().list(maxResults=1).execute()
            return True
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        return self._authenticated and self.creds is not None and not self.creds.expired
