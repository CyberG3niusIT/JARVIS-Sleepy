"""Mobility Planner — general-purpose "how do I get there in time" capability.

Follows the same singleton pattern as core/weather_db.py / core/people_manager.py.
Talks to the existing local WIMAEDV VVS API (see VVS-Beute audit bundle) as a
plain HTTP client against a local service, per task brief section 17: the API
boundary is already clean, no reason to swallow it into this process.

Not school-specific. School (core/school_db.py) is the first caller, but any
skill can build a MobilityRequest (core/mobility_contract.py) and call
plan_arrival() — see skills/system/mobility/skill.py.

Honesty rules this module follows (task brief sections 11/12):
  - Never fabricate a realtime estimate. A leg without an `estimated` time
    from the API is reported as planned/schedule-only for that leg, not
    silently upgraded.
  - Never bridge EFA stop identities to GTFS-RT stop identities ourselves.
    The VVS-Beute audit findings (API_ULTIMATIV_DATA_MODEL_FINDINGS.md,
    section 4 "Stop Resolver Pipeline") are explicit: unresolved identity
    stays unresolved, never guessed. journeys() only uses EFA's own results,
    /stops/*/departures's GTFS-RT delay data is not cross-referenced here.
  - A connection failure to our own API is reported distinctly from a
    failure the API itself reports (e.g. EFA disabled or unreachable).
"""

from __future__ import annotations

import sqlite3
import ipaddress
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, quote
from zoneinfo import ZoneInfo

import requests

from core.logger import get_logger
from core.privacy_gate import get_privacy_gate, Capability
from core.mobility_contract import (
    MobilityRequest,
    MobilityResult,
    MobilityStatus,
    MobilityErrorReason,
    JourneyLeg,
    TravelMode,
)

_instance: Optional["MobilityPlanner"] = None


def get_mobility_planner(config=None) -> Optional["MobilityPlanner"]:
    """Get or create the singleton MobilityPlanner.

    Call with config on first invocation (startup / skill init).
    Call with no args from elsewhere to retrieve the existing instance.
    """
    global _instance
    if _instance is None and config is not None:
        _instance = MobilityPlanner(config)
    return _instance


def reset_mobility_planner_singleton_for_tests() -> None:
    global _instance
    _instance = None


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Parse an EFA ISO timestamp to a NAIVE local (Europe/Berlin) datetime.

    Converts explicitly via zoneinfo rather than just stripping tzinfo, so
    it's correct regardless of whether EFA stamped the value in UTC ('Z')
    or with a local offset. The rest of this JARVIS checkout uses naive
    local datetimes throughout (core/reminder_manager.py) — matching that
    keeps MobilityResult comparable with the rest of the system instead of
    introducing a second, incompatible datetime convention.
    """
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(ZoneInfo("Europe/Berlin"))
        return dt.replace(tzinfo=None)
    except Exception:
        return None


class MobilityPlanner:
    def __init__(self, config):
        self.config = config
        self.logger = get_logger(__name__, config)

        self.enabled = bool(config.get("mobility.enabled", True))
        raw_url = config.get("mobility.base_url") or ""
        raw_url = raw_url.strip() if isinstance(raw_url, str) else ""
        try:
            parsed = urlsplit(raw_url)
            host = parsed.hostname or ""
            loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
            valid_url = (parsed.scheme in {"http", "https"} and loopback and parsed.port != 0
                         and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment)
        except ValueError:
            valid_url = False
        self.base_url = raw_url.rstrip("/") if valid_url and "${" not in raw_url else ""
        raw_key = config.get("mobility.api_key", "") or ""
        self.api_key = raw_key if isinstance(raw_key, str) and "${" not in raw_key else ""
        self.timeout_seconds = float(config.get("mobility.timeout_seconds", 10))
        self.default_arrival_buffer_minutes = int(config.get("mobility.default_arrival_buffer_minutes", 5))
        # stale_after_seconds stays unsupported. Freshness comes from the
        # API's verified GTFS-RT feed state, not a local planner guess.

        self._session = requests.Session()
        self._session.trust_env = False  # Loopback control must never follow an environment proxy.
        if self.api_key:
            self._session.headers["X-API-Key"] = self.api_key

        # Person travel profiles — deliberately NOT school-specific and
        # NOT stored in school.db, per task brief section 9.
        self.db_path = Path(config.get("mobility.db_path") or (Path(config.get("system.storage_path", "/home/alex/jarvis-data")) / "data" / "mobility.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        self._demand_lock = threading.Lock()
        self._demand_last_attempt = None
        self._demand_release_attempt = None
        self._demand_last_status = {"status": "idle", "windows": 0}
        self._demand_needs_release = True  # Revoke a predecessor's lease after restart/privacy lock.

        if not self.base_url:
            self.logger.warning("mobility.base_url not configured — Mobility skill will report 'unavailable'")
        self.logger.info("Mobility planner initialized (base_url=%s)", self.base_url or "<none>")

    # ------------------------------------------------------------------
    # Person profile store
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._conn()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS mobility_profiles (
                        person_id               TEXT PRIMARY KEY,
                        allowed_alone            INTEGER NOT NULL DEFAULT 0,
                        preferred_mode           TEXT,
                        extra_buffer_minutes     INTEGER NOT NULL DEFAULT 0,
                        default_origin_id        TEXT,
                        updated_at               REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS mobility_stop_preferences (
                        canonical_id TEXT PRIMARY KEY, efa_id TEXT NOT NULL,
                        priority INTEGER NOT NULL, pinned INTEGER NOT NULL,
                        recurring INTEGER NOT NULL, verified INTEGER NOT NULL,
                        direction TEXT, updated_at REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS mobility_journey_rules (
                        person_id TEXT NOT NULL, purpose TEXT NOT NULL,
                        weekday INTEGER NOT NULL DEFAULT -1, departure TEXT NOT NULL,
                        origin TEXT NOT NULL, destination TEXT NOT NULL, line TEXT NOT NULL DEFAULT '',
                        priority INTEGER NOT NULL,
                        PRIMARY KEY (person_id, purpose, weekday, departure, origin, destination, line)
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    def get_profile(self, person_id: str) -> dict:
        """Return the person's travel profile, or safe defaults if none is
        set. Default is the conservative one: allowed_alone=False — an
        unconfigured person is never silently assumed independent."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM mobility_profiles WHERE person_id = ?", (person_id,)
            ).fetchone()
            if not row:
                return {
                    "person_id": person_id,
                    "allowed_alone": False,
                    "preferred_mode": None,
                    "extra_buffer_minutes": 0,
                    "default_origin_id": None,
                }
            return dict(row)
        finally:
            conn.close()

    def set_profile(self, person_id: str, allowed_alone: Optional[bool] = None,
                     preferred_mode: Optional[str] = None,
                     extra_buffer_minutes: Optional[int] = None,
                     default_origin_id: Optional[str] = None) -> None:
        current = self.get_profile(person_id)
        merged = {
            "allowed_alone": current["allowed_alone"] if allowed_alone is None else allowed_alone,
            "preferred_mode": current["preferred_mode"] if preferred_mode is None else preferred_mode,
            "extra_buffer_minutes": current["extra_buffer_minutes"] if extra_buffer_minutes is None else extra_buffer_minutes,
            "default_origin_id": current["default_origin_id"] if default_origin_id is None else default_origin_id,
        }
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT INTO mobility_profiles (person_id, allowed_alone, preferred_mode, extra_buffer_minutes, default_origin_id, updated_at) "
                    "VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(person_id) DO UPDATE SET allowed_alone=excluded.allowed_alone, "
                    "preferred_mode=excluded.preferred_mode, extra_buffer_minutes=excluded.extra_buffer_minutes, "
                    "default_origin_id=excluded.default_origin_id, updated_at=excluded.updated_at",
                    (person_id, int(merged["allowed_alone"]), merged["preferred_mode"],
                     merged["extra_buffer_minutes"], merged["default_origin_id"], time.time()),
                )
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # VVS API client
    # ------------------------------------------------------------------

    def set_stop_preference(self, canonical_id, efa_id, priority=100, pinned=False,
                            recurring=False, verified=False, direction=None):
        """Store an explicitly verified canonical/EFA mapping; never resolve by guessing."""
        if not all(isinstance(value, str) and value.strip() for value in (canonical_id, efa_id)):
            raise ValueError("Both stop identifiers are required")
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise ValueError("Priority must be an integer")
        with self._lock:
            conn = self._conn()
            try:
                conn.execute("""INSERT INTO mobility_stop_preferences VALUES (?,?,?,?,?,?,?,?)
                    ON CONFLICT(canonical_id) DO UPDATE SET efa_id=excluded.efa_id,
                    priority=excluded.priority, pinned=excluded.pinned, recurring=excluded.recurring,
                    verified=excluded.verified, direction=excluded.direction, updated_at=excluded.updated_at""",
                    (canonical_id, efa_id, priority, int(bool(pinned)), int(bool(recurring)),
                     int(bool(verified)), direction, time.time()))
                conn.commit()
            finally:
                conn.close()

    def get_stop_preferences(self):
        conn = self._conn()
        try:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM mobility_stop_preferences ORDER BY pinned DESC, priority, canonical_id")]
        finally:
            conn.close()

    def set_journey_rule(self, person_id, purpose, departure, origin, destination,
                         line=None, priority=100, weekday=None):
        """Persist route preferences in mobility.db, referencing existing people IDs.

        weekday is Monday=0 through Sunday=6 or None. Lower priority wins.
        Explicit person rules override '*' rules for the same purpose/day.
        No schedules or family identifiers are shipped as defaults.
        """
        if not all(isinstance(value, str) and value.strip() for value in (person_id, purpose, departure, origin, destination)):
            raise ValueError("Rule requires person, purpose, departure and both stops")
        try:
            parsed_time = datetime.strptime(departure, "%H:%M")
        except ValueError as exc:
            raise ValueError("Departure must be HH:MM") from exc
        if parsed_time.strftime("%H:%M") != departure:
            raise ValueError("Departure must be HH:MM")
        if weekday is not None and (not isinstance(weekday, int) or isinstance(weekday, bool) or not 0 <= weekday <= 6):
            raise ValueError("weekday must be 0..6 or None")
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise ValueError("priority must be an integer")
        if line is not None and not isinstance(line, str):
            raise ValueError("line must be a string or None")
        with self._lock:
            conn = self._conn()
            try:
                conn.execute("""INSERT INTO mobility_journey_rules VALUES (?,?,?,?,?,?,?,?)
                    ON CONFLICT(person_id,purpose,weekday,departure,origin,destination,line)
                    DO UPDATE SET priority=excluded.priority""",
                    (person_id, purpose, -1 if weekday is None else weekday, departure,
                     origin, destination, line or "", priority))
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _event_time(event):
        value = event.get("event_time") if isinstance(event, dict) else None
        if not isinstance(value, datetime):
            raise ValueError("event_time must be a datetime")
        return value.astimezone(ZoneInfo("Europe/Berlin")).replace(tzinfo=None) if value.tzinfo else value

    def get_journey_rules(self, person_id, purpose, weekday):
        conn = self._conn()
        try:
            rows = [dict(row) for row in conn.execute("""SELECT * FROM mobility_journey_rules
                WHERE person_id IN (?, '*') AND purpose=? AND weekday IN (-1, ?)
                ORDER BY priority, departure, origin, destination""", (person_id, purpose, weekday))]
            exact = [row for row in rows if row["person_id"] == person_id]
            rows = exact or rows
            specific_day = [row for row in rows if row["weekday"] == weekday]
            return specific_day or rows
        finally:
            conn.close()

    def _configured_event_rules(self, event):
        when = self._event_time(event)
        person_id, purpose = event.get("person_id"), event.get("purpose")
        if not isinstance(person_id, str) or not person_id or not isinstance(purpose, str) or not purpose:
            raise ValueError("event requires person_id and purpose")
        mappings = {row["canonical_id"]: row for row in self.get_stop_preferences() if row["verified"]}
        return [dict(rule, origin_efa=mappings[rule["origin"]]["efa_id"],
                     destination_efa=mappings[rule["destination"]]["efa_id"],
                     direction=mappings[rule["origin"]].get("direction"))
                for rule in self.get_journey_rules(person_id, purpose, when.weekday())
                if rule["origin"] in mappings and rule["destination"] in mappings]

    @staticmethod
    def _rule_departure(rule, when):
        hour, minute = map(int, rule["departure"].split(":"))
        return when.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def _demand_minutes(self, key, default):
        value = self.config.get("mobility.demand." + key, default)
        return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 1440 else default

    def sync_demand(self, events):
        """Refresh only a local API lease; never fetch journeys or start a worker.

        Called by the existing reminder scheduler. API lease TTL is 900s;
        refresh attempts are spaced >=300s. Empty events/privacy lock revoke.
        Generic config mobility.demand: watch_before_minutes=90,
        active_before_departure_minutes=10,
        end_after_event_minutes=30. Epoch conversion always uses Berlin time.
        Only explicit rules with verified stop mappings create demand.
        """
        with self._demand_lock:
            if not self.enabled or not self.base_url:
                return {"status": "not_configured", "windows": 0}
            if not get_privacy_gate().allow(Capability.REMOTE_TOOL):
                return self._release_demand_locked()
            now = time.time()
            windows = []
            for event in events or []:
                try:
                    when = self._event_time(event)
                    rules = self._configured_event_rules(event)
                except (ValueError, TypeError):
                    continue
                if not rules:
                    continue
                departure = min(self._rule_departure(rule, when) for rule in rules)
                watch_from = when - timedelta(minutes=self._demand_minutes("watch_before_minutes", 90))
                active_from = departure - timedelta(minutes=self._demand_minutes("active_before_departure_minutes", 10))
                end = when + timedelta(minutes=self._demand_minutes("end_after_event_minutes", 30))
                active_from = max(watch_from, active_from)
                if active_from >= end:
                    continue
                epoch = lambda dt: dt.replace(tzinfo=ZoneInfo("Europe/Berlin")).timestamp()
                window = {"start": epoch(watch_from), "end": epoch(end), "active_start": epoch(active_from)}
                if window["end"] > now and window not in windows:
                    windows.append(window)
            windows.sort(key=lambda window: window["start"])
            windows = windows[:128]
            if not windows:
                return self._release_demand_locked()
            if self._demand_last_attempt is not None and now - self._demand_last_attempt < 300:
                return dict(self._demand_last_status, throttled=True)
            self._demand_last_attempt = now
            self._demand_release_attempt = None
            self._demand_needs_release = True
            try:
                response = self._session.post(self.base_url + "/internal/realtime/demand",
                    json={"client_id": "jarvis-school", "windows": windows},
                    timeout=self.timeout_seconds, allow_redirects=False)
                if not 200 <= response.status_code < 300:
                    response.raise_for_status()
                    raise requests.exceptions.RequestException("Demand redirect refused")
                self._demand_last_status = {"status": "registered", "windows": len(windows)}
            except requests.exceptions.RequestException:
                self._demand_last_status = {"status": "unavailable", "windows": 0}
            return dict(self._demand_last_status)

    def _release_demand_locked(self):
        if not self._demand_needs_release:
            return {"status": "idle", "windows": 0}
        now = time.time()
        if self._demand_release_attempt is not None and now - self._demand_release_attempt < 300:
            return dict(self._demand_last_status, throttled=True)
        self._demand_release_attempt = now
        try:
            response = self._session.delete(self.base_url + "/internal/realtime/demand/jarvis-school",
                timeout=self.timeout_seconds, allow_redirects=False)
            if response.status_code != 404 and not 200 <= response.status_code < 300:
                response.raise_for_status()
                raise requests.exceptions.RequestException("Demand redirect refused")
            self._demand_needs_release = False
            self._demand_last_attempt = None
            self._demand_last_status = {"status": "idle", "windows": 0}
        except requests.exceptions.RequestException:
            # A failed revoke is not called success; API TTL remains the backstop.
            self._demand_last_status = {"status": "release_failed", "windows": 0}
        return dict(self._demand_last_status)

    def release_demand(self):
        with self._demand_lock:
            if not self.base_url:
                return {"status": "not_configured", "windows": 0}
            return self._release_demand_locked()

    def plan_school_event(self, event):
        """Query only explicitly configured departures for this School event.

        school_arrival* and school_pickup are arrival deadlines; school_return*
        is departure after school ends. EFA times stay separate from GTFS-RT
        stop updates: no unverified trip-ID joins or fabricated cancellation.
        """
        try:
            when = self._event_time(event)
            rules = self._configured_event_rules(event)
        except (ValueError, TypeError):
            # Invalid external event cannot produce a valid MobilityRequest.
            raise ValueError("School event requires person_id, purpose and datetime event_time")
        purpose = event["purpose"]
        arrival_event = purpose.startswith("school_arrival") or purpose == "school_pickup"
        deadline = when if arrival_event else when.replace(hour=23, minute=59, second=59, microsecond=0)
        request = MobilityRequest(person_id=event["person_id"], purpose=purpose,
            destination_id=rules[0]["destination"] if rules else "", arrive_by=deadline,
            arrival_buffer_minutes=0, event_time=when)
        if not get_privacy_gate().allow(Capability.REMOTE_TOOL):
            return MobilityResult(status=MobilityStatus.UNAVAILABLE, request=request,
                error_reason=MobilityErrorReason.PRIVACY_BLOCKED, message="Mobilitätsabfrage durch Privatsphäre blockiert.")
        if not self.enabled or not self.base_url or not rules:
            return MobilityResult(status=MobilityStatus.UNAVAILABLE, request=request,
                error_reason=MobilityErrorReason.NOT_CONFIGURED,
                message="Keine verifizierte Fahrtregel oder lokale VVS API konfiguriert.")
        failures = []
        canceled_count = 0
        attempted_count = 0
        options = []
        now = datetime.now(ZoneInfo("Europe/Berlin")).replace(tzinfo=None)
        for rule in rules[:8]:
            departure = self._rule_departure(rule, when)
            request = MobilityRequest(person_id=event["person_id"], purpose=purpose,
                origin_id=rule["origin"], destination_id=rule["destination"], arrive_by=deadline,
                arrival_buffer_minutes=0, event_time=when)
            attempted_count += 1
            try:
                scheduled = self._get("/api/v1/stops/" + quote(rule["origin"], safe="") + "/departures",
                    {"at": departure.isoformat(), "limit": 100, "horizon_minutes": 10, "station_scope": "true"})
                if not isinstance(scheduled, dict) or not isinstance(scheduled.get("departures"), list):
                    return self._invalid_response(request)
                candidates = [row for row in scheduled["departures"] if isinstance(row, dict)
                    and _parse_iso(row.get("planned_departure")) == departure
                    and (not rule["line"] or str(row.get("route_short_name") or "") == rule["line"])
                    and (not rule["direction"] or row.get("trip_headsign") == rule["direction"])]
                if not candidates:
                    failures.append(MobilityResult(status=MobilityStatus.UNAVAILABLE, request=request,
                        error_reason=MobilityErrorReason.NO_JOURNEY_FOUND,
                        message="Konfigurierte Abfahrt im Fahrplan nicht bestätigt."))
                    continue
                if len(candidates) != 1:
                    failures.append(MobilityResult(status=MobilityStatus.UNAVAILABLE, request=request,
                        error_reason=MobilityErrorReason.LOCATION_AMBIGUOUS,
                        message="Konfigurierte Abfahrt ist nicht eindeutig; Richtung prüfen."))
                    continue
                candidate = candidates[0]
                feed = scheduled.get("realtime_state")
                feed = feed if isinstance(feed, dict) else {}
                if feed.get("state") == "realtime" and candidate.get("trip_schedule_relationship") == "CANCELED":
                    canceled_count += 1
                    failures.append(MobilityResult(status=MobilityStatus.UNAVAILABLE, request=request,
                        error_reason=MobilityErrorReason.JOURNEY_CANCELED,
                        message="Die konfigurierte Fahrt ist laut aktuellen Echtzeitdaten ausgefallen."))
                    continue
                data = self._get("/api/v1/journeys", {"from": rule["origin_efa"],
                    "to": rule["destination_efa"], "at": departure.isoformat(),
                    "arrive_by": "false", "limit": 5})
            except PermissionError:
                return MobilityResult(status=MobilityStatus.UNAVAILABLE, request=request,
                    error_reason=MobilityErrorReason.PRIVACY_BLOCKED, message="Mobilitätsabfrage durch Privatsphäre blockiert.")
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                return MobilityResult(status=MobilityStatus.UNAVAILABLE, request=request,
                    error_reason=MobilityErrorReason.NOT_CONFIGURED, message="Lokale VVS API nicht erreichbar.")
            except requests.exceptions.HTTPError:
                return MobilityResult(status=MobilityStatus.UNAVAILABLE, request=request,
                    error_reason=MobilityErrorReason.HTTP_ERROR, message="VVS API meldet einen HTTP-Fehler.")
            except ValueError:
                return self._invalid_response(request)
            # Keep late candidates so a delayed primary can still beat a
            # scheduled fallback. Deadline and boardability are evaluated below.
            result = self._normalize_journeys(
                request, data, datetime.max, departure, rule["line"], schedule_structure_only=True)
            if not result.ok:
                failures.append(result)
                continue

            transit_legs = [leg for leg in result.legs if leg.mode == TravelMode.TRANSIT]
            any_estimated = any(
                leg.realtime_departure_at is not None or leg.realtime_arrival_at is not None
                for leg in transit_legs
            )
            route_has_complete_estimates = bool(transit_legs) and all(
                leg.realtime_departure_at is not None and leg.realtime_arrival_at is not None
                for leg in transit_legs
            )
            predicted_departure = _parse_iso(candidate.get("estimated_departure"))
            complete_realtime = (
                feed.get("state") == "realtime"
                and predicted_departure is not None
                and route_has_complete_estimates
            )
            # The configured stop departure is the timetable basis for
            # boarding checks; EFA may prepend a walk leg to the route.
            effective_departure = predicted_departure if complete_realtime else departure
            effective_arrival = result.arrival_at if complete_realtime else result.legs[-1].arrival_at
            if effective_departure is None or effective_arrival is None:
                failures.append(self._invalid_response(request))
                continue
            if effective_departure < now or (not arrival_event and effective_departure < when):
                failures.append(MobilityResult(status=MobilityStatus.UNAVAILABLE, request=request,
                    error_reason=MobilityErrorReason.NO_JOURNEY_FOUND,
                    message="Keine noch erreichbare konfigurierte Abfahrt gefunden."))
                continue
            if effective_arrival > deadline:
                failures.append(MobilityResult(status=MobilityStatus.UNAVAILABLE, request=request,
                    error_reason=MobilityErrorReason.NO_JOURNEY_FOUND,
                    message="Konfigurierte Fahrt erreicht das Schulziel nicht rechtzeitig."))
                continue

            if not complete_realtime:
                # Partial and stale estimates must not leak into either route
                # ranking or the result presented as a departure/arrival.
                for leg in result.legs:
                    leg.realtime_departure_at = None
                    leg.realtime_arrival_at = None
                    leg.delay_minutes = None
                result.leave_at = result.legs[0].departure_at
                result.arrival_at = result.legs[-1].arrival_at
                result.delay_minutes = None
                if feed.get("state") == "stale":
                    result.status = MobilityStatus.DEGRADED
                    result.error_reason = MobilityErrorReason.REALTIME_STALE
                    result.message = "Echtzeitdaten sind veraltet; Auswahl basiert nur auf Fahrplanzeiten."
                elif (feed.get("state") in {"degraded", "unavailable"}
                      or candidate.get("estimated_departure")
                      or (any_estimated and not route_has_complete_estimates)):
                    result.status = MobilityStatus.DEGRADED
                    result.message = "Echtzeitdaten sind unvollständig; Auswahl basiert nur auf Fahrplanzeiten."
                else:
                    result.status = MobilityStatus.SCHEDULE_ONLY
                    result.message = "Für diese Fahrt liegt keine Echtzeitprognose vor; Auswahl basiert nur auf Fahrplanzeiten."
            else:
                result.status = MobilityStatus.REALTIME
                result.leave_at = predicted_departure
                age = feed.get("age_seconds")
                if isinstance(age, (int, float)) and not isinstance(age, bool) and age >= 0:
                    result.data_age_seconds = age
            options.append((effective_arrival, effective_departure, rule.get("priority", 0), result))

        if options:
            return min(options, key=lambda option: (option[0], option[1], option[2]))[3]
        if attempted_count and canceled_count == attempted_count:
            return failures[-1]
        return failures[-1] if failures else MobilityResult(status=MobilityStatus.UNAVAILABLE, request=request,
            error_reason=MobilityErrorReason.NO_JOURNEY_FOUND, message="Keine konfigurierte Abfahrt für dieses Schulereignis bestätigt.")

    def _get(self, path: str, params: dict) -> dict:
        if not self.enabled or not self.base_url:
            raise requests.exceptions.ConnectionError("Local mobility API is not configured")
        if not get_privacy_gate().allow(Capability.REMOTE_TOOL):
            raise PermissionError("Mobility lookup blocked by privacy gate")
        url = f"{self.base_url}{path}"
        resp = self._session.get(url, params=params, timeout=self.timeout_seconds, allow_redirects=False)
        if 300 <= resp.status_code < 400:
            raise requests.exceptions.HTTPError("Mobility API redirect refused", response=resp)
        resp.raise_for_status()
        return resp.json()

    def search_stop(self, query: str, limit: int = 10) -> dict:
        """Thin passthrough to GET /api/v1/stops/search. Raises on failure —
        callers that need the MobilityResult error taxonomy should use
        plan_arrival(); this is for direct lookups (e.g. skill setup)."""
        return self._get("/api/v1/stops/search", {"q": query, "limit": limit, "source": "both"})

    # ------------------------------------------------------------------
    # Journey planning
    # ------------------------------------------------------------------

    def plan_arrival(self, request: MobilityRequest) -> MobilityResult:
        """Resolve a MobilityRequest into a MobilityResult.

        Never raises for expected failure modes (API down, EFA down, no
        journey found, ambiguous location) — those are reported via
        MobilityStatus.UNAVAILABLE + MobilityErrorReason instead, so a
        caller (School or any skill) can render an honest message without
        needing a try/except around every call.
        """
        if not get_privacy_gate().allow(Capability.REMOTE_TOOL):
            return MobilityResult(
                status=MobilityStatus.UNAVAILABLE,
                request=request,
                error_reason=MobilityErrorReason.PRIVACY_BLOCKED,
                message="Mobilitätsplanung ist während der aktuellen Privatsphäre-Einstellung nicht verfügbar.",
            )

        if not self.enabled or not self.base_url:
            return MobilityResult(
                status=MobilityStatus.UNAVAILABLE,
                request=request,
                error_reason=MobilityErrorReason.NOT_CONFIGURED,
                message="Mobility ist nicht konfiguriert (mobility.base_url fehlt).",
            )

        profile = self.get_profile(request.person_id)
        origin_id = request.origin_id or profile.get("default_origin_id")
        if not origin_id:
            return MobilityResult(
                status=MobilityStatus.UNAVAILABLE,
                request=request,
                error_reason=MobilityErrorReason.NOT_CONFIGURED,
                message=f"Kein Startort für {request.person_id} bekannt (weder in der Anfrage noch im Profil hinterlegt).",
            )

        try:
            buffers = (request.arrival_buffer_minutes, profile.get("extra_buffer_minutes", 0))
            if not isinstance(request.arrive_by, datetime) or any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in buffers
            ):
                raise ValueError("Invalid arrival time or buffer")
            arrive_by = request.arrive_by
            if arrive_by.tzinfo is not None:
                arrive_by = arrive_by.astimezone(ZoneInfo("Europe/Berlin")).replace(tzinfo=None)
            query_target = arrive_by - timedelta(minutes=sum(buffers))
        except (TypeError, ValueError, OverflowError):
            return MobilityResult(
                status=MobilityStatus.UNAVAILABLE, request=request,
                error_reason=MobilityErrorReason.INVALID_REQUEST,
                message="Ankunftszeit oder Zeitpuffer ist ungültig.",
            )

        try:
            data = self._get("/api/v1/journeys", {
                "from": origin_id,
                "to": request.destination_id,
                "at": query_target.isoformat(),
                "arrive_by": "true",
                "limit": 5,
            })
        except requests.exceptions.ConnectionError:
            return MobilityResult(
                status=MobilityStatus.UNAVAILABLE, request=request,
                error_reason=MobilityErrorReason.NOT_CONFIGURED,
                message="Die WIMAEDV VVS API ist nicht erreichbar.",
            )
        except requests.exceptions.Timeout:
            return MobilityResult(
                status=MobilityStatus.UNAVAILABLE, request=request,
                error_reason=MobilityErrorReason.NOT_CONFIGURED,
                message="Die WIMAEDV VVS API hat nicht rechtzeitig geantwortet.",
            )
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else None
            return MobilityResult(
                status=MobilityStatus.UNAVAILABLE, request=request,
                error_reason=MobilityErrorReason.HTTP_ERROR,
                message=f"VVS API meldet einen Fehler (HTTP {code}).",
            )
        except ValueError:
            # requests JSONDecodeError inherits ValueError. A reachable
            # server returning invalid JSON is not an unreachable server.
            return self._invalid_response(request)
        except Exception as e:
            self.logger.error("Unerwarteter Fehler bei /api/v1/journeys: %s", e)
            return MobilityResult(
                status=MobilityStatus.UNAVAILABLE, request=request,
                error_reason=MobilityErrorReason.API_UNREACHABLE,
                message="Unerwarteter Fehler bei der Verbindungsanfrage.",
            )

        return self._normalize_journeys(request, data, query_target)

    def _normalize_journeys(self, request, data, query_target, preferred_departure=None,
                            preferred_line=None, schedule_structure_only=False):
        if not isinstance(data, dict) or not isinstance(data.get("journeys"), list):
            return self._invalid_response(request)
        journeys = data["journeys"]
        if not journeys:
            return MobilityResult(
                status=MobilityStatus.UNAVAILABLE, request=request,
                error_reason=MobilityErrorReason.NO_JOURNEY_FOUND,
                message="Keine passende Verbindung gefunden.",
            )

        # Do not rely on API ranking or assume arrive_by was honored. Choose
        # the latest feasible departure using effective times, including delay.
        candidates = []
        malformed = False
        for journey in journeys:
            raw = journey.get("legs") if isinstance(journey, dict) else None
            if not isinstance(raw, list) or not raw:
                malformed = True
                continue
            effective = []
            for leg in raw:
                if not isinstance(leg, dict) or any(not isinstance(leg.get(key), dict) for key in ("origin", "destination", "transport")):
                    break
                dep = (_parse_iso(leg["origin"].get("planned")) if schedule_structure_only else
                       _parse_iso(leg["origin"].get("estimated")) or _parse_iso(leg["origin"].get("planned")))
                arr = (_parse_iso(leg["destination"].get("planned")) if schedule_structure_only else
                       _parse_iso(leg["destination"].get("estimated")) or _parse_iso(leg["destination"].get("planned")))
                if dep is None or arr is None or dep > arr or (effective and dep < effective[-1][1]):
                    break
                effective.append((dep, arr))
            if len(effective) != len(raw):
                malformed = True
                continue
            if preferred_departure is not None:
                transit = next((leg for leg in raw if leg["transport"].get("line") or leg["transport"].get("product_class") is not None), None)
                if transit is None or _parse_iso(transit["origin"].get("planned")) != preferred_departure:
                    continue
                if preferred_line and str(transit["transport"].get("line") or "") != preferred_line:
                    continue
            if effective[-1][1] <= query_target:
                candidates.append((effective[0][0], raw))
        if not candidates and malformed:
            return self._invalid_response(request)
        legs_raw = max(candidates, key=lambda item: item[0])[1] if candidates else []
        if not legs_raw:
            return MobilityResult(
                status=MobilityStatus.UNAVAILABLE, request=request,
                error_reason=MobilityErrorReason.NO_JOURNEY_FOUND,
                message="Verbindung ohne Teilstrecken zurückgeliefert.",
            )

        legs: list[JourneyLeg] = []
        any_estimated = False
        all_estimated = True
        transit_count = 0
        for leg in legs_raw:
            transport = leg.get("transport") or {}
            origin_pt = leg.get("origin") or {}
            dest_pt = leg.get("destination") or {}
            # Heuristic, not confirmed against a live EFA response (VVS-Beute
            # only contains the API's source code, not a captured journeys()
            # payload): a leg with neither a line/product_class is treated
            # as a walking leg. If this proves wrong against real EFA data,
            # fix here — do not guess further downstream.
            is_transit = bool(transport.get("line")) or transport.get("product_class") is not None
            mode = TravelMode.TRANSIT if is_transit else TravelMode.WALK

            dep_planned = _parse_iso(origin_pt.get("planned"))
            dep_est = _parse_iso(origin_pt.get("estimated"))
            arr_planned = _parse_iso(dest_pt.get("planned"))
            arr_est = _parse_iso(dest_pt.get("estimated"))

            if is_transit:
                transit_count += 1
                any_estimated |= dep_est is not None or arr_est is not None
                all_estimated &= dep_est is not None and arr_est is not None
            delay_seconds = dest_pt.get("delay_seconds")
            if not isinstance(delay_seconds, (int, float)) or isinstance(delay_seconds, bool):
                delay_seconds = None

            legs.append(JourneyLeg(
                mode=mode,
                line=transport.get("line"),
                from_stop=origin_pt.get("name"),
                to_stop=dest_pt.get("name"),
                departure_at=dep_planned,
                arrival_at=arr_planned,
                realtime_departure_at=dep_est,
                realtime_arrival_at=arr_est,
                delay_minutes=(delay_seconds // 60) if delay_seconds is not None else None,
            ))

        first_leg, last_leg = legs[0], legs[-1]
        leave_at = first_leg.realtime_departure_at or first_leg.departure_at
        arrival_at = last_leg.realtime_arrival_at or last_leg.arrival_at
        delay_minutes = last_leg.delay_minutes

        if all_estimated and transit_count:
            status = MobilityStatus.REALTIME
        elif any_estimated:
            status = MobilityStatus.DEGRADED
        else:
            status = MobilityStatus.SCHEDULE_ONLY

        message = ""
        system_messages = data.get("system_messages") or []
        if not isinstance(system_messages, list):
            system_messages = []
        if system_messages:
            message = "Hinweis der VVS: " + "; ".join(
                str(m.get("text") or m) if isinstance(m, dict) else str(m) for m in system_messages
            )

        return MobilityResult(
            status=status,
            request=request,
            leave_at=leave_at,
            arrival_at=arrival_at,
            delay_minutes=delay_minutes,
            legs=legs,
            message=message,
        )

    @staticmethod
    def _invalid_response(request: MobilityRequest) -> MobilityResult:
        return MobilityResult(
            status=MobilityStatus.UNAVAILABLE, request=request,
            error_reason=MobilityErrorReason.INVALID_RESPONSE,
            message="Die VVS API hat keine auswertbare Verbindung geliefert.",
        )
