"""Unit tests for core.capabilities.vocabulary (syntax and vocabulary rules)."""

from __future__ import annotations

import pytest

from core.capabilities.vocabulary import (
    CAPABILITY_VERBS,
    CapabilityContractError,
    CapabilityId,
    ExecutionContext,
    MergeSemantics,
    RiskFlag,
    check_closed_fields,
    parse_privacy_refs,
    parse_risk_flags,
    validate_egress_host,
    validate_risk_invariants,
    validate_secret_ref,
)


# ---------------------------------------------------------------------------
# CapabilityId
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [
    "calendar.read",
    "desktop.application.launch",
    "filesystem.update",
    "a1.b_2.status",
])
def test_capability_id_accepts_valid_values(value):
    assert str(CapabilityId(value)) == value


@pytest.mark.parametrize("value", [
    "Calendar.read",            # uppercase
    "calendar.Read",
    "read",                     # one segment
    "a.b.c.read",               # four segments
    "calendar..read",           # empty segment
    "calendar.",
    ".read",
    "calendar.fly",             # verb not in CAPABILITY_VERBS
    "calendar.v1.read",         # version segment
    "google.calendar.read",     # reserved provider name
    "calendar.read\n",          # trailing newline must not slip through
    "1calendar.read",
    "calendar read",
])
def test_capability_id_rejects_invalid_values(value):
    with pytest.raises(CapabilityContractError):
        CapabilityId(value)


@pytest.mark.parametrize("value", [None, 5, b"calendar.read", ["calendar.read"]])
def test_capability_id_rejects_non_string(value):
    with pytest.raises(CapabilityContractError):
        CapabilityId(value)
    with pytest.raises(CapabilityContractError):
        CapabilityId.parse(value)


def test_capability_id_parse_is_idempotent():
    first = CapabilityId.parse("calendar.read")
    assert CapabilityId.parse(first) is first
    assert CapabilityId.parse(str(first)) == first


def test_capability_id_verb_and_str():
    cid = CapabilityId("desktop.application.launch")
    assert cid.verb == "launch"
    assert cid.verb in CAPABILITY_VERBS
    assert str(cid) == "desktop.application.launch"


def test_capability_id_ordering_and_equality():
    ids = [CapabilityId("calendar.update"), CapabilityId("calendar.read"),
           CapabilityId("audio.read")]
    assert [i.value for i in sorted(ids)] == [
        "audio.read", "calendar.read", "calendar.update"]
    assert CapabilityId("calendar.read") == CapabilityId("calendar.read")
    assert len({CapabilityId("calendar.read"), CapabilityId("calendar.read")}) == 1


# ---------------------------------------------------------------------------
# RiskFlag
# ---------------------------------------------------------------------------

def test_risk_flag_names_and_members():
    assert {f.name for f in RiskFlag} == {
        "READ", "WRITE", "DESTRUCTIVE", "SENSITIVE", "PRIVILEGED",
        "EXTERNAL_EFFECT"}
    assert all(f.value == f.name for f in RiskFlag)


def test_parse_risk_flags_accepts_names_and_members():
    parsed = parse_risk_flags(["READ", RiskFlag.WRITE, "READ"])
    assert parsed == frozenset({RiskFlag.READ, RiskFlag.WRITE})
    assert parse_risk_flags(flag for flag in ["SENSITIVE"]) == frozenset(
        {RiskFlag.SENSITIVE})
    assert parse_risk_flags([]) == frozenset()


@pytest.mark.parametrize("raw", [["read"], ["NETWORK"], ["READ", "bogus"], [""]])
def test_parse_risk_flags_unknown_fails_closed(raw):
    with pytest.raises(CapabilityContractError):
        parse_risk_flags(raw)


@pytest.mark.parametrize("raw", ["READ", b"READ", 5, None])
def test_parse_risk_flags_rejects_non_collection(raw):
    with pytest.raises(CapabilityContractError):
        parse_risk_flags(raw)


@pytest.mark.parametrize("raw", [[1], [None], [b"READ"], [["READ"]]])
def test_parse_risk_flags_rejects_non_string_element(raw):
    with pytest.raises(CapabilityContractError):
        parse_risk_flags(raw)


@pytest.mark.parametrize("flags", [
    frozenset(),
    frozenset({RiskFlag.SENSITIVE}),
    frozenset({RiskFlag.PRIVILEGED, RiskFlag.EXTERNAL_EFFECT}),
    frozenset({RiskFlag.DESTRUCTIVE}),
    frozenset({RiskFlag.READ, RiskFlag.DESTRUCTIVE}),
])
def test_validate_risk_invariants_rejects_invalid_sets(flags):
    with pytest.raises(CapabilityContractError):
        validate_risk_invariants(flags)


@pytest.mark.parametrize("flags", [
    frozenset({RiskFlag.READ}),
    frozenset({RiskFlag.WRITE}),
    frozenset({RiskFlag.READ, RiskFlag.SENSITIVE}),
    frozenset({RiskFlag.WRITE, RiskFlag.DESTRUCTIVE}),
])
def test_validate_risk_invariants_accepts_valid_sets(flags):
    assert validate_risk_invariants(flags) == flags


# ---------------------------------------------------------------------------
# ExecutionContext and MergeSemantics
# ---------------------------------------------------------------------------

def test_execution_context_parse_names_and_members():
    for ctx in ExecutionContext:
        assert ExecutionContext.parse(ctx.name) is ctx
        assert ExecutionContext.parse(ctx) is ctx


def test_execution_context_rank_order():
    assert (ExecutionContext.LOCAL.rank < ExecutionContext.LAN.rank
            < ExecutionContext.NETWORK.rank < ExecutionContext.CLOUD.rank)
    assert [c.rank for c in ExecutionContext] == [0, 1, 2, 3]


@pytest.mark.parametrize("raw", ["local", "Local", "UNKNOWN", "", None, 1])
def test_execution_context_parse_rejects_unknown(raw):
    with pytest.raises(CapabilityContractError):
        ExecutionContext.parse(raw)


def test_merge_semantics_parse():
    assert MergeSemantics.parse("NONE") is MergeSemantics.NONE
    assert MergeSemantics.parse(MergeSemantics.UNION) is MergeSemantics.UNION


@pytest.mark.parametrize("raw", ["union", "none", "MERGE", "", None, 1])
def test_merge_semantics_parse_rejects_unknown(raw):
    with pytest.raises(CapabilityContractError):
        MergeSemantics.parse(raw)


# ---------------------------------------------------------------------------
# Axis orthogonality
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["NETWORK", "CLOUD", "LAN", "REMOTE_TOOL"])
def test_risk_flags_carry_no_execution_context_names(name):
    assert name not in RiskFlag.__members__


def test_risk_and_context_axes_are_disjoint():
    risk_names = {f.name for f in RiskFlag}
    context_names = {c.name for c in ExecutionContext}
    assert risk_names.isdisjoint(context_names)


def test_external_effect_alone_implies_no_context():
    flags = validate_risk_invariants(
        parse_risk_flags(["READ", "EXTERNAL_EFFECT"]))
    assert RiskFlag.EXTERNAL_EFFECT in flags
    # The flag set offers no way to read an execution context out of it.
    assert not any(isinstance(item, ExecutionContext) for item in flags)


# ---------------------------------------------------------------------------
# Privacy references
# ---------------------------------------------------------------------------

def test_parse_privacy_refs_accepts_upper_snake_case():
    assert parse_privacy_refs(["CALENDAR_DATA", "A", "A1_B2", "A"]) == frozenset(
        {"CALENDAR_DATA", "A", "A1_B2"})
    assert parse_privacy_refs([]) == frozenset()


@pytest.mark.parametrize("ref", [
    "lower", "Mixed_Case", "A__B", "_A", "A_", "", "1A", "A-B", "A B", "A\n",
    5, None, b"A",
])
def test_parse_privacy_refs_rejects_bad_names(ref):
    with pytest.raises(CapabilityContractError):
        parse_privacy_refs([ref])


@pytest.mark.parametrize("raw", ["CALENDAR_DATA", b"CALENDAR_DATA", 5, None])
def test_parse_privacy_refs_rejects_single_value_as_collection(raw):
    with pytest.raises(CapabilityContractError):
        parse_privacy_refs(raw)


# ---------------------------------------------------------------------------
# Secret references
# ---------------------------------------------------------------------------

def test_validate_secret_ref_accepts_valid_reference():
    assert validate_secret_ref("secretref:calendar_token") == "secretref:calendar_token"
    assert validate_secret_ref("secretref:a") == "secretref:a"
    longest = "secretref:a" + "b" * 63
    assert validate_secret_ref(longest) == longest


@pytest.mark.parametrize("value", [
    "calendar_token",               # no prefix
    "secretref:Calendar_Token",     # uppercase
    "secretref:has space",
    "secretref:",
    "secretref:1abc",
    "secretref:_abc",
    "secretref:a" + "b" * 64,       # 65 chars after prefix
    "secretref:calendar_token\n",   # fullmatch must reject the newline
    " secretref:calendar_token",
    None,
    5,
])
def test_validate_secret_ref_rejects_invalid_values(value):
    with pytest.raises(CapabilityContractError):
        validate_secret_ref(value)


# ---------------------------------------------------------------------------
# Egress hosts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("host", [
    "example.org", "sub.example.org", "192.0.2.10", "::1", "localhost",
    "a-b.example.org",
])
def test_validate_egress_host_accepts_valid_hosts(host):
    assert validate_egress_host(host) == host


@pytest.mark.parametrize("host", [
    "https://example.org",
    "example.org/path",
    "example.org:443",
    "user@example.org",
    "example .org",
    " example.org",
    "",
    "my_host.example.org",          # underscore
    "-a.example.org",               # leading hyphen in label
    "a-.example.org",               # trailing hyphen in label
    "1.2.3.999",                    # numeric TLD, not a valid IP
    "example.org.",                 # empty trailing label
    "example..org",
    "example.org\n",                # trailing newline
    ".".join(["a" * 63] * 4),       # longer than 253 characters
    None,
    5,
])
def test_validate_egress_host_rejects_invalid_hosts(host):
    with pytest.raises(CapabilityContractError):
        validate_egress_host(host)


# ---------------------------------------------------------------------------
# Closed schemas
# ---------------------------------------------------------------------------

_REQ = frozenset({"a", "b"})
_OPT = frozenset({"c"})


def _check(data):
    return check_closed_fields(data, required=_REQ, optional=_OPT, label="thing")


def test_check_closed_fields_accepts_valid_mappings():
    assert _check({"a": 1, "b": 2}) is None
    assert _check({"a": 1, "b": 2, "c": 3}) is None


@pytest.mark.parametrize("data", [None, [], "a", 5, (("a", 1),)])
def test_check_closed_fields_rejects_non_mapping(data):
    with pytest.raises(CapabilityContractError, match="thing"):
        _check(data)


def test_check_closed_fields_rejects_unknown_field():
    with pytest.raises(CapabilityContractError, match="unknown"):
        _check({"a": 1, "b": 2, "zzz": 3})


def test_check_closed_fields_rejects_missing_required_field():
    with pytest.raises(CapabilityContractError, match="missing"):
        _check({"a": 1})


def test_check_closed_fields_rejects_non_string_key():
    with pytest.raises(CapabilityContractError, match="strings"):
        _check({"a": 1, "b": 2, 3: 4})
