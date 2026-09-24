"""School Database — deterministic school-day state model.

Follows the same singleton + threading.Lock + sqlite3 pattern as
core/weather_db.py, core/people_manager.py and core/reminder_manager.py.
All private schedule/child/location data lives under the configured
storage path (school.db_path, defaulting under storage_path), never in
this repository, never in fixtures, never in defaults.

Layering (highest priority first — see task brief section 5):

    1. override           — explicit, per-day, per-person correction
    2. school_message     — a confirmed message from the school for that day
    3. special_rule       — durable rule (school-wide or per person)
    4. regular_schedule    — the baseline weekly timetable

A period existing in the regular schedule does NOT automatically mean a
pickup is needed at its end time — a voluntary period ("freiwillig") does
not count toward the effective school-end time unless a higher layer says
otherwise. See resolve_day() / DayStatus.
"""

from __future__ import annotations

import enum
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime, time as time_cls
from pathlib import Path
from typing import Optional

from core.logger import get_logger

_instance: Optional["SchoolDB"] = None


def get_school_db(config=None) -> Optional["SchoolDB"]:
    """Get or create the singleton SchoolDB.

    Call with config on first invocation (startup / skill init).
    Call with no args from elsewhere to retrieve the existing instance.
    """
    global _instance
    if _instance is None and config is not None:
        _instance = SchoolDB(config)
    return _instance


def reset_school_db_singleton_for_tests() -> None:
    """Test-only: drop the singleton so a fresh SchoolDB can be created
    against a temp DB. Never call from production code."""
    global _instance
    _instance = None


class Provenance(str, enum.Enum):
    REGULAR_SCHEDULE = "regular_schedule"
    SPECIAL_RULE = "special_rule"
    SCHOOL_MESSAGE = "school_message"
    OVERRIDE = "override"


@dataclass
class DayStatus:
    """Resolved, deterministic state for one person on one date."""

    person_id: str
    date: date_cls
    school_end: Optional[time_cls] = None
    school_end_approximate: bool = False
    pickup_required: Optional[bool] = None
    independent_return_allowed: Optional[bool] = None
    canceled: bool = False
    note: str = ""
    provenance: Provenance = Provenance.REGULAR_SCHEDULE
    confidence: float = 1.0
    periods: list[dict] = field(default_factory=list)  # raw regular-schedule periods, for callers that need detail


class SchoolDB:
    """Deterministic school state store + resolver."""

    def __init__(self, config):
        self.config = config
        self.logger = get_logger(__name__, config)

        configured_path = config.get("school.db_path")
        if not configured_path or str(configured_path).startswith("${"):
            storage = config.get("system.storage_path")
            if not storage or str(storage).startswith("${"):
                raise ValueError("school.db_path or system.storage_path must be configured")
            configured_path = Path(storage) / "data" / "school.db"
        self.db_path = Path(configured_path).expanduser().resolve()
        repository = Path(__file__).resolve().parent.parent
        if self.db_path.is_relative_to(repository):
            raise ValueError("School data must be stored outside the repository")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        self.logger.info("School database initialized")

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._conn()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS regular_schedule (
                        id              TEXT PRIMARY KEY,
                        person_id       TEXT NOT NULL,
                        weekday         INTEGER NOT NULL,  -- 0=Monday .. 6=Sunday
                        start_time      TEXT NOT NULL,     -- HH:MM
                        end_time        TEXT NOT NULL,     -- HH:MM
                        label           TEXT,
                        mandatory       INTEGER NOT NULL DEFAULT 1,
                        created_at      REAL NOT NULL,
                        updated_at      REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS special_rules (
                        id                          TEXT PRIMARY KEY,
                        person_id                   TEXT,       -- NULL = school-wide
                        weekday                     INTEGER,    -- NULL = every day
                        rule_type                   TEXT NOT NULL,  -- e.g. 'pickup_required', 'independent_return_allowed', 'school_end_override'
                        value                       TEXT NOT NULL,  -- JSON-ish scalar as text; interpreted by rule_type
                        note                        TEXT,
                        valid_from                  TEXT,       -- ISO date, NULL = unbounded
                        valid_until                 TEXT,       -- ISO date, NULL = unbounded
                        created_at                  REAL NOT NULL,
                        updated_at                  REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS day_events (
                        id              TEXT PRIMARY KEY,
                        person_id       TEXT,       -- NULL = affects everyone
                        event_date      TEXT NOT NULL,  -- ISO date
                        rule_type       TEXT NOT NULL,  -- same vocabulary as special_rules.rule_type
                        value           TEXT NOT NULL,
                        confirmed       INTEGER NOT NULL DEFAULT 0,  -- only confirmed messages outrank special_rules
                        confidence      REAL NOT NULL DEFAULT 1.0,
                        source          TEXT,       -- free text: where this came from
                        note            TEXT,
                        created_at      REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS overrides (
                        id              TEXT PRIMARY KEY,
                        person_id       TEXT,       -- NULL = affects everyone
                        event_date      TEXT NOT NULL,  -- ISO date
                        rule_type       TEXT NOT NULL,
                        value           TEXT NOT NULL,
                        note            TEXT,
                        created_by      TEXT,       -- who entered this override
                        created_at      REAL NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_regsched_person_wd ON regular_schedule(person_id, weekday)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_special_person ON special_rules(person_id, weekday)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_events_person_date ON day_events(person_id, event_date)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_overrides_person_date ON overrides(person_id, event_date)")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS travel_requirements (
                        id TEXT PRIMARY KEY,
                        person_id TEXT NOT NULL,
                        purpose TEXT NOT NULL CHECK (purpose IN ('school_return_midday', 'school_arrival_afternoon')),
                        period_id TEXT NOT NULL REFERENCES regular_schedule(id) ON DELETE CASCADE,
                        created_at REAL NOT NULL,
                        UNIQUE(person_id, purpose, period_id)
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Writers
    # ------------------------------------------------------------------

    def add_regular_period(self, person_id: str, weekday: int, start_time: str,
                            end_time: str, label: str = "", mandatory: bool = True) -> str:
        """Add one period to the baseline weekly timetable.

        weekday: 0=Monday .. 6=Sunday. mandatory=False marks a voluntary
        period that does not count toward the effective school-end time.
        """
        if not (0 <= weekday <= 6):
            raise ValueError("weekday must be 0..6 (Monday..Sunday)")
        self._validate_time(start_time)
        self._validate_time(end_time)
        if end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        pid = str(uuid.uuid4())
        now = time.time()
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT INTO regular_schedule "
                    "(id, person_id, weekday, start_time, end_time, label, mandatory, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (pid, person_id, weekday, start_time, end_time, label, int(mandatory), now, now),
                )
                conn.commit()
            finally:
                conn.close()
        return pid

    def add_special_rule(self, rule_type: str, value: str, person_id: Optional[str] = None,
                          weekday: Optional[int] = None, note: str = "",
                          valid_from: Optional[str] = None, valid_until: Optional[str] = None) -> str:
        """Add a durable special rule. person_id=None applies to everyone."""
        self._validate_rule(rule_type, value)
        rid = str(uuid.uuid4())
        now = time.time()
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT INTO special_rules "
                    "(id, person_id, weekday, rule_type, value, note, valid_from, valid_until, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (rid, person_id, weekday, rule_type, value, note, valid_from, valid_until, now, now),
                )
                conn.commit()
            finally:
                conn.close()
        return rid

    def add_day_event(self, event_date: str, rule_type: str, value: str,
                       person_id: Optional[str] = None, confirmed: bool = False,
                       confidence: float = 1.0, source: str = "", note: str = "") -> str:
        """Record a concrete, dated event (e.g. a school announcement).

        Only confirmed=True events outrank special_rules in resolve_day();
        unconfirmed events are visible via list_day_events() but do not
        change the resolved DayStatus, so an unverified rumour never
        silently changes whether a child gets picked up.
        """
        self._validate_rule(rule_type, value)
        eid = str(uuid.uuid4())
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT INTO day_events "
                    "(id, person_id, event_date, rule_type, value, confirmed, confidence, source, note, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (eid, person_id, event_date, rule_type, value, int(confirmed), confidence, source, note, time.time()),
                )
                conn.commit()
            finally:
                conn.close()
        return eid

    def add_override(self, event_date: str, rule_type: str, value: str,
                      person_id: Optional[str] = None, note: str = "", created_by: str = "") -> str:
        """Add an explicit temporary override. Always wins over everything
        else for the given (person_id or everyone, event_date, rule_type)."""
        self._validate_rule(rule_type, value)
        oid = str(uuid.uuid4())
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT INTO overrides "
                    "(id, person_id, event_date, rule_type, value, note, created_by, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (oid, person_id, event_date, rule_type, value, note, created_by, time.time()),
                )
                conn.commit()
            finally:
                conn.close()
        return oid

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def _fetch_layer_value(self, conn, table: str, person_id: str, event_date: date_cls,
                            rule_type: str, extra_where: str = "", confirmed_only: bool = False):
        """Return the most specific matching row's value for a rule_type
        in `table`, preferring a row scoped to person_id over a global
        (person_id IS NULL) one. Returns None if nothing matches."""
        date_str = event_date.isoformat()
        confirmed_clause = "AND confirmed = 1" if confirmed_only else ""
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE rule_type = ? AND event_date = ? "
            f"AND (person_id = ? OR person_id IS NULL) {confirmed_clause} {extra_where} "
            f"ORDER BY (person_id IS NULL) ASC, created_at DESC",
            (rule_type, date_str, person_id),
        ).fetchall()
        return rows[0] if rows else None

    def resolve_day(self, person_id: str, on_date: date_cls) -> DayStatus:
        """Resolve the deterministic DayStatus for one person and date,
        applying the override > school_message > special_rule > regular_schedule
        priority stack per rule_type independently — a temporary override
        of `pickup_required` does not silently also override `school_end`.
        """
        conn = self._conn()
        try:
            weekday = on_date.weekday()

            periods = [dict(r) for r in conn.execute(
                "SELECT * FROM regular_schedule WHERE person_id = ? AND weekday = ? ORDER BY start_time",
                (person_id, weekday),
            ).fetchall()]

            status = DayStatus(person_id=person_id, date=on_date, periods=periods)

            # --- school_end: last mandatory period's end, from regular schedule ---
            mandatory_ends = [p["end_time"] for p in periods if p["mandatory"]]
            for end in mandatory_ends:
                self._validate_time(end)
            if mandatory_ends:
                latest = max(mandatory_ends)
                h, m = (int(x) for x in latest.split(":"))
                status.school_end = time_cls(hour=h, minute=m)
                status.provenance = Provenance.REGULAR_SCHEDULE

            # --- apply special_rules (durable), scoped by weekday + validity window ---
            date_str = on_date.isoformat()
            for rule_type in ("school_end", "school_end_approximate", "pickup_required", "independent_return_allowed", "canceled"):
                rows = conn.execute(
                    "SELECT * FROM special_rules WHERE rule_type = ? "
                    "AND (person_id = ? OR person_id IS NULL) "
                    "AND (weekday IS NULL OR weekday = ?) "
                    "AND (valid_from IS NULL OR valid_from <= ?) "
                    "AND (valid_until IS NULL OR valid_until >= ?) "
                    "ORDER BY (person_id IS NULL) ASC, updated_at DESC",
                    (rule_type, person_id, weekday, date_str, date_str),
                ).fetchall()
                if rows:
                    self._apply_value(status, rule_type, rows[0]["value"], Provenance.SPECIAL_RULE, 1.0)
                    if rows[0]["note"]:
                        status.note = rows[0]["note"]

            # --- apply confirmed school_message day_events (outrank special_rules only) ---
            for rule_type in ("school_end", "school_end_approximate", "pickup_required", "independent_return_allowed", "canceled"):
                row = self._fetch_layer_value(conn, "day_events", person_id, on_date, rule_type, confirmed_only=True)
                if row:
                    self._apply_value(status, rule_type, row["value"], Provenance.SCHOOL_MESSAGE, row["confidence"])
                    if row["note"]:
                        status.note = row["note"]

            # --- apply overrides (always wins) ---
            for rule_type in ("school_end", "school_end_approximate", "pickup_required", "independent_return_allowed", "canceled"):
                row = self._fetch_layer_value(conn, "overrides", person_id, on_date, rule_type)
                if row:
                    self._apply_value(status, rule_type, row["value"], Provenance.OVERRIDE, 1.0)
                    if row["note"]:
                        status.note = row["note"]

            # pickup_required / independent_return_allowed have no baseline value
            # from the regular schedule (that's a person-level default, not a
            # per-period fact) — if nothing set it, leave it as None rather than
            # guessing, so callers can see "not configured" instead of a
            # silently-wrong default.
            return status
        finally:
            conn.close()

    @staticmethod
    def _validate_time(value: str) -> None:
        if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("School times must use HH:MM")

    @staticmethod
    def _validate_rule(rule_type: str, value: str) -> None:
        if rule_type == "school_end":
            SchoolDB._validate_time(value)
        elif rule_type in ("school_end_approximate", "pickup_required", "independent_return_allowed", "canceled"):
            if not isinstance(value, str) or value.strip().lower() not in (
                "1", "true", "yes", "ja", "0", "false", "no", "nein"
            ):
                raise ValueError("School boolean rule must explicitly be true or false")
        else:
            raise ValueError("Unknown school rule_type")

    @staticmethod
    def _apply_value(status: DayStatus, rule_type: str, value: str, provenance: Provenance, confidence: float):
        SchoolDB._validate_rule(rule_type, value)
        if rule_type == "school_end":
            h, m = (int(x) for x in value.split(":"))
            status.school_end = time_cls(hour=h, minute=m)
        elif rule_type == "pickup_required":
            status.pickup_required = value.strip().lower() in ("1", "true", "yes", "ja")
        elif rule_type == "independent_return_allowed":
            status.independent_return_allowed = value.strip().lower() in ("1", "true", "yes", "ja")
        elif rule_type == "canceled":
            status.canceled = value.strip().lower() in ("1", "true", "yes", "ja")
        elif rule_type == "school_end_approximate":
            status.school_end_approximate = value.strip().lower() in ("1", "true", "yes", "ja")
        status.provenance = provenance
        status.confidence = confidence

    def list_day_events(self, person_id: str, on_date: date_cls) -> list[dict]:
        """All day_events (confirmed or not) for a person/date, newest first.
        Useful for surfacing an unconfirmed rumour to a human without letting
        it silently change resolve_day()'s output."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM day_events WHERE (person_id = ? OR person_id IS NULL) AND event_date = ? "
                "ORDER BY created_at DESC",
                (person_id, on_date.isoformat()),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    def add_travel_requirement(self, person_id: str, purpose: str, period_id: str) -> str:
        """Bind an additional return to an existing mandatory school period.

        The referenced period supplies the weekday and end time. Permission
        to return independently is resolved separately for each actual date.
        """
        if purpose not in ("school_return_midday", "school_arrival_afternoon"):
            raise ValueError("Unsupported school travel purpose")
        requirement_id = str(uuid.uuid4())
        with self._lock:
            conn = self._conn()
            try:
                period = conn.execute(
                    "SELECT person_id, mandatory FROM regular_schedule WHERE id = ?",
                    (period_id,),
                ).fetchone()
                if period is None or period["person_id"] != person_id or not period["mandatory"]:
                    raise ValueError("Travel requirement needs this person's mandatory period")
                conn.execute(
                    "INSERT INTO travel_requirements (id, person_id, purpose, period_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (requirement_id, person_id, purpose, period_id, time.time()),
                )
                conn.commit()
            finally:
                conn.close()
        return requirement_id

    def travel_events(self, on_date: date_cls) -> list[dict]:
        """Return school-derived travel times, without routes or destinations.

        A canceled day emits nothing. Unknown pickup/return rules never imply
        permission to travel alone. Midday returns require explicit selection
        of a mandatory period and cannot outlive an earlier resolved school end.
        Times are naive school-local datetimes, matching resolve_day's contract.
        """
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT person_id FROM regular_schedule UNION "
                "SELECT person_id FROM special_rules WHERE person_id IS NOT NULL UNION "
                "SELECT person_id FROM day_events WHERE person_id IS NOT NULL UNION "
                "SELECT person_id FROM overrides WHERE person_id IS NOT NULL"
            ).fetchall()
            requirements = conn.execute("SELECT person_id, purpose, period_id FROM travel_requirements").fetchall()
        finally:
            conn.close()
        events = []
        for row in rows:
            status = self.resolve_day(row["person_id"], on_date)
            if status.canceled:
                continue
            events.extend(self._day_travel_events(status, requirements))
        return sorted(events, key=lambda event: (event["event_time"], event["person_id"], event["purpose"]))

    def _day_travel_events(self, status: DayStatus, requirements: list) -> list[dict]:
        mandatory = {period["id"]: period for period in status.periods if period["mandatory"]}
        events = []

        def add(purpose: str, event_time: time_cls) -> None:
            event = {"person_id": status.person_id, "purpose": purpose,
                     "event_time": datetime.combine(status.date, event_time)}
            if event not in events:
                events.append(event)

        if mandatory:
            for period in mandatory.values():
                self._validate_time(period["start_time"])
            add("school_arrival", time_cls.fromisoformat(min(p["start_time"] for p in mandatory.values())))
        if status.school_end is not None:
            if status.pickup_required is True:
                add("school_pickup", status.school_end)
            elif status.independent_return_allowed is True:
                add("school_return", status.school_end)
            if status.independent_return_allowed is True:
                for requirement in requirements:
                    if requirement["person_id"] != status.person_id:
                        continue
                    period = mandatory.get(requirement["period_id"])
                    if period is not None:
                        time_key = "start_time" if requirement["purpose"] == "school_arrival_afternoon" else "end_time"
                        self._validate_time(period[time_key])
                        required_time = time_cls.fromisoformat(period[time_key])
                        if required_time < status.school_end:
                            add(requirement["purpose"], required_time)
        return events
