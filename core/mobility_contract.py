"""Shared contract between the School skill (or any other requester) and
the Mobility planner.

This module intentionally contains NO business logic and NO network code.
It exists so that School (core/school_db.py, skills/personal/school) and
Mobility (core/mobility_planner.py, skills/system/mobility) can depend on
the same small set of types without depending on each other. Anything that
needs to ask "how do I get somewhere by a given time" builds a
MobilityRequest and gets back a MobilityResult; School is just the first
caller, not a hardcoded one (see skills/system/mobility/skill.py which
builds requests directly, without any School involvement).

Keep this file small. If a new field is needed, it almost certainly
belongs here rather than being smuggled into a skill-specific dict, so
that both sides keep agreeing on the same shape.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class MobilityStatus(str, enum.Enum):
    """How the MobilityResult was derived. Never invent a better status
    than the data actually supports (see KNOWN_LIMITATIONS.md of the
    WIMAEDV VVS API: no fabricated realtime)."""

    REALTIME = "realtime"          # Based on live GTFS-RT / EFA realtime data
    SCHEDULE_ONLY = "schedule_only"  # Static timetable only, no realtime signal available
    DEGRADED = "degraded"          # Partial estimated timestamps
    UNAVAILABLE = "unavailable"    # No usable result at all (see MobilityErrorReason)


class MobilityErrorReason(str, enum.Enum):
    """Populated only when MobilityStatus is UNAVAILABLE or the journey
    itself is unusable. Mirrors section 12 of the task brief 1:1 so the
    caller can render an honest message instead of a generic failure."""

    API_UNREACHABLE = "api_unreachable"
    EFA_UNREACHABLE = "efa_unreachable"
    STATIC_DATA_STALE = "static_data_stale"  # Not emitted: static age metadata is absent
    REALTIME_STALE = "realtime_stale"  # Emitted when the configured realtime feed is stale
    INVALID_RESPONSE = "invalid_response"
    INVALID_REQUEST = "invalid_request"
    HTTP_ERROR = "http_error"
    NO_JOURNEY_FOUND = "no_journey_found"
    LOCATION_AMBIGUOUS = "location_ambiguous"
    JOURNEY_CANCELED = "journey_canceled"  # Emitted only for explicit GTFS-RT CANCELED relationship
    PRIVACY_BLOCKED = "privacy_blocked"
    NOT_CONFIGURED = "not_configured"


class TravelMode(str, enum.Enum):
    WALK = "walk"
    TRANSIT = "transit"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MobilityRequest:
    """What the requester (School or anything else) asks for.

    Deliberately does NOT contain a line/bus number or a route — that is
    Mobility's job to work out. See task brief section 8: School expresses
    intent, not a transit plan.
    """

    person_id: str
    purpose: str                      # e.g. "school_pickup", "school_dropoff", "appointment"
    destination_id: str               # a place identifier the Mobility layer can resolve
    arrive_by: datetime                # the person must be AT destination_id by this time
    origin_id: Optional[str] = None    # if None, Mobility resolves the person's current/home origin
    arrival_buffer_minutes: int = 5
    event_time: Optional[datetime] = None  # the underlying event this trip serves, for logging/traceability
    request_id: Optional[str] = None


@dataclass
class JourneyLeg:
    """One leg of a journey. Intentionally loose (mode/line as free text)
    because EFA's leg vocabulary varies by product type; Mobility should
    not force a leg into a shape the source data doesn't support."""

    mode: TravelMode
    line: Optional[str] = None
    from_stop: Optional[str] = None
    to_stop: Optional[str] = None
    departure_at: Optional[datetime] = None
    arrival_at: Optional[datetime] = None
    realtime_departure_at: Optional[datetime] = None
    realtime_arrival_at: Optional[datetime] = None
    delay_minutes: Optional[int] = None
    canceled: Optional[bool] = None  # Unknown until a verified source field exists


@dataclass
class MobilityResult:
    """What Mobility hands back. `status` and `error_reason` together tell
    the caller exactly how much to trust `leave_at`."""

    status: MobilityStatus
    request: MobilityRequest
    leave_at: Optional[datetime] = None
    arrival_at: Optional[datetime] = None
    delay_minutes: Optional[int] = None
    legs: list[JourneyLeg] = field(default_factory=list)
    error_reason: Optional[MobilityErrorReason] = None
    message: str = ""              # short human-readable explanation, German, no TTS formatting
    data_age_seconds: Optional[float] = None

    @property
    def ok(self) -> bool:
        return self.status != MobilityStatus.UNAVAILABLE and self.leave_at is not None
