"""Vocabulary of the capability contract layer.

Capability identifiers, action risk flags, execution contexts, merge semantics
and the syntax rules for privacy references, secret references and egress
hosts. Pure data and validation: no I/O, no registry, no runtime hooks.

Action risk, execution context and privacy references are independent axes.
Nothing here derives one from another.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CapabilityContractError(ValueError):
    """Base class for every contract violation raised by this package."""


# ---------------------------------------------------------------------------
# Capability identifiers
# ---------------------------------------------------------------------------

CAPABILITY_VERBS = frozenset({
    "read", "list", "search", "create", "update",
    "delete", "send", "launch", "control", "status",
})

# A capability id names what can be done, never who does it. Well-known
# provider names are therefore rejected as a domain segment. This is a guard
# against a common mistake, not a proof that an id is provider-neutral.
RESERVED_PROVIDER_SEGMENTS = frozenset({
    "google", "microsoft", "apple", "nextcloud", "anthropic", "openai",
    "caldav", "outlook", "icloud",
})

_SEGMENT = re.compile(r"[a-z][a-z0-9_]*")
_VERSION_SEGMENT = re.compile(r"v[0-9]+")


@dataclass(frozen=True, order=True)
class CapabilityId:
    """Stable, provider-neutral capability identifier such as ``calendar.read``.

    Two or three lowercase segments, the last one a verb from
    ``CAPABILITY_VERBS``. No version and no provider identity in the id.
    """

    value: str

    def __post_init__(self) -> None:
        value = self.value
        if not isinstance(value, str):
            raise CapabilityContractError("capability id must be a string")
        segments = value.split(".")
        if not 2 <= len(segments) <= 3:
            raise CapabilityContractError(
                f"capability id '{value}' must have 2 or 3 dot-separated segments")
        for segment in segments:
            if not _SEGMENT.fullmatch(segment):
                raise CapabilityContractError(
                    f"capability id '{value}' has an invalid segment '{segment}'")
            if _VERSION_SEGMENT.fullmatch(segment):
                raise CapabilityContractError(
                    f"capability id '{value}' must not carry a version segment")
        if segments[-1] not in CAPABILITY_VERBS:
            raise CapabilityContractError(
                f"capability id '{value}' must end in one of: "
                f"{', '.join(sorted(CAPABILITY_VERBS))}")
        reserved = RESERVED_PROVIDER_SEGMENTS.intersection(segments[:-1])
        if reserved:
            raise CapabilityContractError(
                f"capability id '{value}' must not contain a provider identity "
                f"({', '.join(sorted(reserved))})")

    @classmethod
    def parse(cls, raw: "CapabilityId | str") -> "CapabilityId":
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, str):
            return cls(raw)
        raise CapabilityContractError("capability id must be a string")

    @property
    def verb(self) -> str:
        return self.value.rsplit(".", 1)[1]

    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# Action risk
# ---------------------------------------------------------------------------

class RiskFlag(Enum):
    """What an action does. Independent of where it runs.

    ``EXTERNAL_EFFECT`` describes the effect of an action beyond the user's own
    data (visible to third parties or the physical world). It does not mean
    network, cloud or remote tool.
    """

    READ = "READ"
    WRITE = "WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"
    SENSITIVE = "SENSITIVE"
    PRIVILEGED = "PRIVILEGED"
    EXTERNAL_EFFECT = "EXTERNAL_EFFECT"


def parse_risk_flags(raw: Iterable["RiskFlag | str"]) -> frozenset[RiskFlag]:
    """Parse flag names or members. Unknown flags fail closed."""
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Iterable):
        raise CapabilityContractError("risk flags must be a collection of flag names")
    flags: set[RiskFlag] = set()
    for item in raw:
        if isinstance(item, RiskFlag):
            flags.add(item)
        elif isinstance(item, str):
            try:
                flags.add(RiskFlag[item])
            except KeyError:
                raise CapabilityContractError(f"unknown risk flag '{item}'") from None
        else:
            raise CapabilityContractError("risk flag must be a string")
    return frozenset(flags)


def validate_risk_invariants(flags: frozenset[RiskFlag]) -> frozenset[RiskFlag]:
    """Check the structural rules every risk set has to satisfy."""
    if not flags.intersection({RiskFlag.READ, RiskFlag.WRITE}):
        raise CapabilityContractError("risk must include READ or WRITE")
    if RiskFlag.DESTRUCTIVE in flags and RiskFlag.WRITE not in flags:
        raise CapabilityContractError("DESTRUCTIVE requires WRITE")
    return flags


# ---------------------------------------------------------------------------
# Execution context and merge semantics
# ---------------------------------------------------------------------------

class ExecutionContext(Enum):
    """Where a provider runs or reaches. A property of the provider."""

    LOCAL = "LOCAL"
    LAN = "LAN"
    NETWORK = "NETWORK"
    CLOUD = "CLOUD"

    @property
    def rank(self) -> int:
        return _CONTEXT_ORDER.index(self)

    @classmethod
    def parse(cls, raw: "ExecutionContext | str") -> "ExecutionContext":
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, str):
            try:
                return cls[raw]
            except KeyError:
                pass
        raise CapabilityContractError(f"unknown execution context '{raw}'")


_CONTEXT_ORDER = (
    ExecutionContext.LOCAL,
    ExecutionContext.LAN,
    ExecutionContext.NETWORK,
    ExecutionContext.CLOUD,
)


class MergeSemantics(Enum):
    """Declared vocabulary only. No merge logic exists in this package."""

    NONE = "NONE"
    UNION = "UNION"

    @classmethod
    def parse(cls, raw: "MergeSemantics | str") -> "MergeSemantics":
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, str):
            try:
                return cls[raw]
            except KeyError:
                pass
        raise CapabilityContractError(f"unknown merge semantics '{raw}'")


# Flags that rule out UNION: results of such capabilities must not be merged.
MERGE_FORBIDDEN_FLAGS = frozenset({
    RiskFlag.WRITE, RiskFlag.DESTRUCTIVE, RiskFlag.EXTERNAL_EFFECT,
})


# ---------------------------------------------------------------------------
# Syntax-only references
# ---------------------------------------------------------------------------

_PRIVACY_REF = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*")
_SECRET_REF = re.compile(r"secretref:[a-z][a-z0-9_]{0,63}")
_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def parse_privacy_refs(raw: Iterable[str]) -> frozenset[str]:
    """Check UPPER_SNAKE_CASE syntax only.

    The names are not checked against any privacy implementation and no
    privacy decision is made here.
    """
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Iterable):
        raise CapabilityContractError("privacy references must be a collection of names")
    refs: set[str] = set()
    for item in raw:
        if not isinstance(item, str) or not _PRIVACY_REF.fullmatch(item):
            raise CapabilityContractError(
                f"privacy reference {item!r} must be UPPER_SNAKE_CASE")
        refs.add(item)
    return frozenset(refs)


def validate_secret_ref(value: str) -> str:
    """Check the syntax of an opaque secret reference.

    A reference names a secret; it never contains one. Only the syntax is
    checked. Nothing is read, resolved or stored.
    """
    if not isinstance(value, str) or not _SECRET_REF.fullmatch(value):
        raise CapabilityContractError(
            "secret reference must look like 'secretref:<lowercase_name>'")
    return value


def validate_egress_host(value: str) -> str:
    """Check that a value is a plain host name or IP literal."""
    if not isinstance(value, str) or not value or len(value) > 253:
        raise CapabilityContractError("egress host must be a non-empty host name or IP")
    if "%" in value:
        raise CapabilityContractError("egress host must not carry an interface scope")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        pass
    labels = value.split(".")
    if not all(_HOST_LABEL.fullmatch(label) for label in labels):
        raise CapabilityContractError(f"egress host '{value}' is not a valid host name")
    if labels[-1].isdigit():
        raise CapabilityContractError(f"egress host '{value}' is not a valid host name")
    return value


# ---------------------------------------------------------------------------
# Closed schemas
# ---------------------------------------------------------------------------

def check_closed_fields(
    data: Any,
    *,
    required: frozenset[str],
    optional: frozenset[str],
    label: str,
) -> None:
    """Reject anything that is not a mapping with exactly the declared fields."""
    if not isinstance(data, Mapping):
        raise CapabilityContractError(f"{label} must be a mapping")
    if not all(isinstance(key, str) for key in data):
        raise CapabilityContractError(f"{label} field names must be strings")
    unknown = set(data) - required - optional
    if unknown:
        raise CapabilityContractError(
            f"{label}: unknown field(s): {', '.join(sorted(unknown))}")
    missing = required - set(data)
    if missing:
        raise CapabilityContractError(
            f"{label}: missing field(s): {', '.join(sorted(missing))}")
