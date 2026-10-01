"""Unit tests for the declarative provider manifest and the core capability spec.

Covers the closed manifest schema, version and identifier syntax, execution
context and egress rules, secret reference syntax, additive risk, merge
semantics, determinism and immutability, plus CapabilitySpec validation.
No I/O beyond reading the JSON fixtures.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.capabilities.contract import (
    CapabilitySpec,
    ProviderContract,
    ProviderDescriptor,
)
from core.capabilities.manifest import (
    MANIFEST_SCHEMA_VERSION,
    ManifestError,
    ProviderManifest,
)
from core.capabilities.vocabulary import (
    CapabilityContractError,
    CapabilityId,
    ExecutionContext,
    MergeSemantics,
    RiskFlag,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "capabilities"


def _load_json(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _manifest(**overrides):
    """Minimal valid manifest mapping, with overrides applied on top."""
    data = {
        "schema_version": 1,
        "provider_version": "1.0.0",
        "provider_id": "test_provider",
        "provides": ["calendar.read"],
        "execution_context": "LOCAL",
    }
    data.update(overrides)
    return data


def _build(**overrides) -> ProviderManifest:
    return ProviderManifest.from_mapping(_manifest(**overrides))


def _spec_mapping(**overrides):
    data = {
        "id": "calendar.read",
        "contract_version": 1,
        "minimum_risk": ["READ"],
        "privacy_policy_refs": ["CALENDAR_CONTENT"],
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Fixture manifest
# ---------------------------------------------------------------------------

@pytest.fixture
def fixture_manifest() -> ProviderManifest:
    return ProviderManifest.from_mapping(_load_json("example_provider_manifest.json"))


def test_fixture_manifest_loads_core_fields(fixture_manifest):
    assert fixture_manifest.schema_version == MANIFEST_SCHEMA_VERSION == 1
    assert fixture_manifest.provider_version == "0.1.0"
    assert fixture_manifest.provider_id == "example_local_calendar"


def test_fixture_manifest_provides_sorted_capability_ids(fixture_manifest):
    provides = fixture_manifest.describe().provides
    assert provides == (
        CapabilityId("calendar.list"),
        CapabilityId("calendar.read"),
        CapabilityId("calendar.search"),
    )
    assert isinstance(provides, tuple)


def test_fixture_manifest_context_and_merge(fixture_manifest):
    descriptor = fixture_manifest.describe()
    assert descriptor.execution_context is ExecutionContext.LOCAL
    assert descriptor.merge_semantics is MergeSemantics.UNION
    assert descriptor.egress_hosts == ()
    assert descriptor.secret_refs == ()


def test_fixture_manifest_additional_risk_for_read(fixture_manifest):
    descriptor = fixture_manifest.describe()
    assert descriptor.additional_risk_for("calendar.read") == frozenset({RiskFlag.SENSITIVE})
    assert descriptor.additional_risk_for(CapabilityId("calendar.read")) == frozenset(
        {RiskFlag.SENSITIVE})


@pytest.mark.parametrize("capability", ["calendar.list", "calendar.search", "calendar.create"])
def test_fixture_manifest_has_no_other_additional_risk(fixture_manifest, capability):
    assert fixture_manifest.describe().additional_risk_for(capability) == frozenset()


def test_describe_returns_descriptor(fixture_manifest):
    descriptor = fixture_manifest.describe()
    assert isinstance(descriptor, ProviderDescriptor)
    assert descriptor is fixture_manifest.descriptor


def test_manifest_satisfies_provider_contract_protocol(fixture_manifest):
    assert isinstance(fixture_manifest, ProviderContract)


def test_descriptor_has_no_field_to_state_or_lower_risk():
    names = {f.name for f in dataclasses.fields(ProviderDescriptor)}
    assert "additional_risk" in names
    assert not names & {"minimum_risk", "declared_risk", "risk"}


# ---------------------------------------------------------------------------
# Closed schema
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field",
    ["declared_risk", "created_by", "generator", "build_id", "signature",
     "minimum_risk", "egress_host", "Schema_Version"],
)
def test_unknown_field_rejected(field):
    with pytest.raises(ManifestError, match="unknown field"):
        ProviderManifest.from_mapping(_manifest(**{field: "x"}))


@pytest.mark.parametrize(
    "field",
    ["schema_version", "provider_id", "provider_version", "provides", "execution_context"],
)
def test_missing_required_field_rejected(field):
    data = _manifest()
    del data[field]
    with pytest.raises(ManifestError, match="missing field"):
        ProviderManifest.from_mapping(data)


def test_optional_fields_take_defaults():
    manifest = _build()
    descriptor = manifest.describe()
    assert dict(descriptor.additional_risk) == {}
    assert descriptor.egress_hosts == ()
    assert descriptor.secret_refs == ()
    assert descriptor.merge_semantics is MergeSemantics.NONE


@pytest.mark.parametrize("data", [None, [], "manifest", 5, ("a", "b")])
def test_non_mapping_rejected(data):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(data)


def test_non_string_field_name_rejected():
    data = _manifest()
    data[1] = "x"
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(data)


def test_manifest_error_is_contract_error_and_value_error():
    assert issubclass(ManifestError, CapabilityContractError)
    assert issubclass(ManifestError, ValueError)


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("version", [2, 0, True, "1", None, 1.5, [1]])
def test_schema_version_rejected(version):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(schema_version=version))


@pytest.mark.parametrize(
    "version",
    ["1.0", "v1.0.0", "01.0.0", "1.0.0-rc1", "1.0.0.0", "1.a.0", "", " 1.0.0", None, 1, 1.0],
)
def test_provider_version_rejected(version):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(provider_version=version))


@pytest.mark.parametrize("version", ["0.0.0", "1.0.0", "10.20.30", "0.1.0"])
def test_provider_version_accepted(version):
    assert _build(provider_version=version).provider_version == version


# ---------------------------------------------------------------------------
# Provider id
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "provider_id",
    [
        pytest.param("Upper", id="uppercase"),
        pytest.param("with-dash", id="dash"),
        pytest.param("a", id="too-short"),
        pytest.param("a" * 65, id="too-long"),
        pytest.param("1abc", id="digit-first"),
        pytest.param("_abc", id="underscore-first"),
        pytest.param("has space", id="space"),
        pytest.param("", id="empty"),
        pytest.param(None, id="none"),
        pytest.param(["abc"], id="list"),
    ],
)
def test_provider_id_rejected(provider_id):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(provider_id=provider_id))


@pytest.mark.parametrize("provider_id", ["ab", "a" * 64, "a1_b2", "example_local_calendar"])
def test_provider_id_accepted(provider_id):
    assert _build(provider_id=provider_id).provider_id == provider_id


# ---------------------------------------------------------------------------
# provides
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "provides",
    [
        pytest.param([], id="empty"),
        pytest.param(["calendar.read", "calendar.read"], id="duplicates"),
        pytest.param("calendar.read", id="string-instead-of-list"),
        pytest.param({"calendar.read": 1}, id="mapping"),
        pytest.param(None, id="none"),
        pytest.param(5, id="int"),
        pytest.param(["Calendar.Read"], id="uppercase-syntax"),
        pytest.param(["calendar.Read"], id="uppercase-verb"),
        pytest.param(["calendar"], id="single-segment"),
        pytest.param(["calendar.explode"], id="unknown-verb"),
        pytest.param(["google.calendar.read"], id="provider-identity"),
        pytest.param(["calendar.v2.read"], id="version-segment"),
        pytest.param(["a.b.c.read"], id="four-segments"),
        pytest.param(["calendar..read"], id="empty-segment"),
        pytest.param(["1calendar.read"], id="digit-first-segment"),
        pytest.param(["calendar.read "], id="trailing-space"),
        pytest.param(["calendar.read", 5], id="non-string-entry"),
        pytest.param([["calendar.read"]], id="nested-list"),
    ],
)
def test_provides_rejected(provides):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(provides=provides))


def test_provides_accepts_tuple_and_sorts():
    manifest = _build(provides=("calendar.search", "calendar.list", "calendar.read"))
    assert [str(c) for c in manifest.describe().provides] == [
        "calendar.list", "calendar.read", "calendar.search"]


# ---------------------------------------------------------------------------
# Execution context and egress hosts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("context", ["UNKNOWN", "local", "Local", "", "REMOTE", 1, None, {}])
def test_execution_context_rejected(context):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(execution_context=context))


@pytest.mark.parametrize(
    ("context", "hosts", "valid"),
    [
        ("LOCAL", [], True),
        ("LOCAL", ["example.com"], False),
        ("LAN", [], True),
        ("LAN", ["nas.local"], True),
        ("NETWORK", [], False),
        ("NETWORK", ["api.example.com"], True),
        ("CLOUD", [], False),
        ("CLOUD", ["cloud.example.com"], True),
    ],
)
def test_context_egress_host_matrix(context, hosts, valid):
    data = _manifest(execution_context=context, egress_hosts=hosts)
    if valid:
        manifest = ProviderManifest.from_mapping(data)
        assert manifest.describe().execution_context is ExecutionContext[context]
        assert manifest.describe().egress_hosts == tuple(hosts)
    else:
        with pytest.raises(ManifestError):
            ProviderManifest.from_mapping(data)


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("https://example.com", id="url"),
        pytest.param("example.com:8080", id="port"),
        pytest.param("example.com/path", id="path"),
        pytest.param("user@example.com", id="userinfo"),
        pytest.param("", id="empty"),
        pytest.param("exa mple.com", id="space"),
        pytest.param("-bad.example.com", id="leading-dash-label"),
        pytest.param("example..com", id="empty-label"),
        pytest.param("example.com.", id="trailing-dot"),
        pytest.param("Example.com", id="uppercase"),
        pytest.param("*.example.com", id="wildcard"),
        pytest.param("1.2.3.999", id="numeric-tld"),
        pytest.param("a" * 254, id="too-long"),
        pytest.param(5, id="non-string"),
    ],
)
def test_egress_host_rejected(host):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(
            _manifest(execution_context="NETWORK", egress_hosts=[host]))


@pytest.mark.parametrize(
    "host", ["example.com", "192.168.1.10", "::1", "localhost", "a-b.example.org"])
def test_egress_host_accepted(host):
    manifest = _build(execution_context="CLOUD", egress_hosts=[host])
    assert manifest.describe().egress_hosts == (host,)


def test_egress_hosts_duplicates_rejected():
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(
            execution_context="NETWORK",
            egress_hosts=["a.example.com", "a.example.com"]))


@pytest.mark.parametrize("hosts", ["api.example.com", None, {"api.example.com"}])
def test_egress_hosts_must_be_list(hosts):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(
            _manifest(execution_context="NETWORK", egress_hosts=hosts))


# ---------------------------------------------------------------------------
# Secret references
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "ref",
    ["secretref:calendar_token", "secretref:a", "secretref:a1_b2", "secretref:" + "a" * 64],
)
def test_secret_ref_accepted(ref):
    assert _build(secret_refs=[ref]).describe().secret_refs == (ref,)


@pytest.mark.parametrize(
    "ref",
    [
        pytest.param("hunter2", id="plain-password"),
        pytest.param("sk-abc", id="api-key-like"),
        pytest.param("secretref:", id="empty-name"),
        pytest.param("secretref:Upper", id="uppercase-name"),
        pytest.param("secretref:1abc", id="digit-first"),
        pytest.param("SECRETREF:token", id="uppercase-prefix"),
        pytest.param("secretref:tok-en", id="dash"),
        pytest.param("secretref:tok en", id="space"),
        pytest.param("secretref:" + "a" * 65, id="too-long"),
        pytest.param("", id="empty"),
        pytest.param(5, id="non-string"),
    ],
)
def test_secret_ref_rejected(ref):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(secret_refs=[ref]))


def test_secret_refs_duplicates_rejected():
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(
            secret_refs=["secretref:token", "secretref:token"]))


def test_secret_refs_sorted_and_must_be_list():
    manifest = _build(secret_refs=["secretref:b_token", "secretref:a_token"])
    assert manifest.describe().secret_refs == ("secretref:a_token", "secretref:b_token")
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(secret_refs="secretref:token"))


# ---------------------------------------------------------------------------
# additional_risk
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "additional",
    [
        pytest.param({"calendar.read": ["SUPERUSER"]}, id="unknown-flag"),
        pytest.param({"calendar.read": ["sensitive"]}, id="lowercase-flag"),
        pytest.param({"calendar.create": ["SENSITIVE"]}, id="capability-not-provided"),
        pytest.param(["SENSITIVE"], id="list-instead-of-mapping"),
        pytest.param("SENSITIVE", id="string-instead-of-mapping"),
        pytest.param(None, id="none"),
        pytest.param(5, id="int"),
        pytest.param({"calendar.read": "SENSITIVE"}, id="flag-list-as-single-string"),
        pytest.param({"calendar.read": None}, id="flags-none"),
        pytest.param({"calendar.read": [1]}, id="non-string-flag"),
        pytest.param({"calendar.read": {"SENSITIVE"}}, id="flags-as-set"),
        pytest.param({"Calendar.Read": ["SENSITIVE"]}, id="invalid-capability-key"),
        pytest.param({1: ["SENSITIVE"]}, id="non-string-capability-key"),
    ],
)
def test_additional_risk_rejected(additional):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(additional_risk=additional))


def test_additional_risk_accepts_several_flags():
    manifest = _build(additional_risk={"calendar.read": ["SENSITIVE", "PRIVILEGED"]})
    assert manifest.describe().additional_risk_for("calendar.read") == frozenset(
        {RiskFlag.SENSITIVE, RiskFlag.PRIVILEGED})


def test_additional_risk_only_adds_what_is_declared():
    manifest = _build(
        provides=["calendar.read", "calendar.list"],
        additional_risk={"calendar.read": ["SENSITIVE"]})
    descriptor = manifest.describe()
    assert descriptor.additional_risk_for("calendar.read") == frozenset({RiskFlag.SENSITIVE})
    assert descriptor.additional_risk_for("calendar.list") == frozenset()
    assert list(descriptor.additional_risk) == [CapabilityId("calendar.read")]


# ---------------------------------------------------------------------------
# merge_semantics
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("flag", ["WRITE", "DESTRUCTIVE", "EXTERNAL_EFFECT"])
def test_union_with_forbidden_additional_risk_rejected(flag):
    with pytest.raises(ManifestError, match="UNION"):
        ProviderManifest.from_mapping(_manifest(
            merge_semantics="UNION", additional_risk={"calendar.read": [flag]}))


def test_union_with_forbidden_flag_among_allowed_rejected():
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(
            merge_semantics="UNION",
            additional_risk={"calendar.read": ["SENSITIVE", "WRITE"]}))


@pytest.mark.parametrize("flags", [["SENSITIVE"], ["PRIVILEGED"], ["READ"], []])
def test_union_with_harmless_additional_risk_accepted(flags):
    manifest = _build(merge_semantics="UNION", additional_risk={"calendar.read": flags})
    assert manifest.describe().merge_semantics is MergeSemantics.UNION


@pytest.mark.parametrize("flag", ["WRITE", "DESTRUCTIVE", "EXTERNAL_EFFECT"])
def test_merge_none_allows_write_like_additional_risk(flag):
    manifest = _build(merge_semantics="NONE", additional_risk={"calendar.read": [flag]})
    assert manifest.describe().merge_semantics is MergeSemantics.NONE
    assert RiskFlag[flag] in manifest.describe().additional_risk_for("calendar.read")


@pytest.mark.parametrize("value", ["MERGE", "union", "Union", "", None, 1])
def test_merge_semantics_rejected(value):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(merge_semantics=value))


# ---------------------------------------------------------------------------
# Determinism and immutability
# ---------------------------------------------------------------------------

def test_permuted_input_yields_identical_descriptor_values():
    first = _build(
        provides=["calendar.search", "calendar.read", "calendar.list"],
        execution_context="NETWORK",
        egress_hosts=["b.example.com", "a.example.com"],
        secret_refs=["secretref:b_token", "secretref:a_token"],
        additional_risk={"calendar.search": ["SENSITIVE"], "calendar.read": ["PRIVILEGED"]})
    second = _build(
        provides=["calendar.list", "calendar.read", "calendar.search"],
        execution_context="NETWORK",
        egress_hosts=["a.example.com", "b.example.com"],
        secret_refs=["secretref:a_token", "secretref:b_token"],
        additional_risk={"calendar.read": ["PRIVILEGED"], "calendar.search": ["SENSITIVE"]})
    a, b = first.describe(), second.describe()
    assert a.provides == b.provides
    assert a.egress_hosts == b.egress_hosts == ("a.example.com", "b.example.com")
    assert a.secret_refs == b.secret_refs
    assert list(a.additional_risk) == list(b.additional_risk)
    assert dict(a.additional_risk) == dict(b.additional_risk)


def test_flag_order_in_input_does_not_matter():
    first = _build(additional_risk={"calendar.read": ["SENSITIVE", "PRIVILEGED"]})
    second = _build(additional_risk={"calendar.read": ["PRIVILEGED", "SENSITIVE"]})
    assert first.describe().additional_risk_for("calendar.read") == \
        second.describe().additional_risk_for("calendar.read")


def test_descriptor_is_frozen():
    descriptor = _build().describe()
    with pytest.raises(FrozenInstanceError):
        descriptor.provider_id = "other_provider"
    with pytest.raises(FrozenInstanceError):
        descriptor.egress_hosts = ("example.com",)


def test_manifest_is_frozen():
    manifest = _build()
    with pytest.raises(FrozenInstanceError):
        manifest.provider_version = "9.9.9"
    with pytest.raises(FrozenInstanceError):
        manifest.descriptor = None


def test_additional_risk_is_read_only():
    descriptor = _build(additional_risk={"calendar.read": ["SENSITIVE"]}).describe()
    with pytest.raises(TypeError):
        descriptor.additional_risk[CapabilityId("calendar.read")] = frozenset()
    with pytest.raises(TypeError):
        del descriptor.additional_risk[CapabilityId("calendar.read")]


def test_provides_tuple_is_immutable():
    descriptor = _build().describe()
    with pytest.raises(TypeError):
        descriptor.provides[0] = CapabilityId("calendar.list")


def test_mutating_input_after_build_changes_nothing():
    raw = _manifest(
        provides=["calendar.read", "calendar.list"],
        additional_risk={"calendar.read": ["SENSITIVE"]})
    manifest = ProviderManifest.from_mapping(raw)
    raw["provides"].append("calendar.search")
    raw["additional_risk"]["calendar.read"].append("PRIVILEGED")
    descriptor = manifest.describe()
    assert len(descriptor.provides) == 2
    assert descriptor.additional_risk_for("calendar.read") == frozenset({RiskFlag.SENSITIVE})


# ---------------------------------------------------------------------------
# Errors are always ManifestError for malformed input
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"provides": None}, id="provides-none"),
        pytest.param({"provides": [["x"]]}, id="provides-nested"),
        pytest.param({"additional_risk": None}, id="additional-risk-none"),
        pytest.param({"additional_risk": {"calendar.read": None}}, id="flags-none"),
        pytest.param({"additional_risk": {1: ["SENSITIVE"]}}, id="capability-key-int"),
        pytest.param({"egress_hosts": None}, id="egress-none"),
        pytest.param({"secret_refs": None}, id="secret-refs-none"),
        pytest.param({"merge_semantics": None}, id="merge-none"),
        pytest.param({"execution_context": {}}, id="context-mapping"),
        pytest.param({"provider_id": []}, id="provider-id-list"),
        pytest.param({"provider_version": ["1.0.0"]}, id="version-list"),
        pytest.param({"schema_version": None}, id="schema-none"),
    ],
)
def test_malformed_input_raises_manifest_error_not_raw_exceptions(overrides):
    with pytest.raises(ManifestError):
        ProviderManifest.from_mapping(_manifest(**overrides))


# ---------------------------------------------------------------------------
# CapabilitySpec
# ---------------------------------------------------------------------------

def test_fixture_specs_load():
    specs = [CapabilitySpec.from_mapping(d) for d in _load_json("calendar_specs.json")]
    assert len(specs) == 6
    assert len({s.id for s in specs}) == 6
    for spec in specs:
        assert spec.minimum_risk & {RiskFlag.READ, RiskFlag.WRITE}
        assert spec.privacy_policy_refs == frozenset({"CALENDAR_CONTENT"})
        assert spec.contract_version == 1


def test_fixture_specs_risk_content():
    specs = {str(s.id): s for s in
             (CapabilitySpec.from_mapping(d) for d in _load_json("calendar_specs.json"))}
    for read_like in ("calendar.list", "calendar.read", "calendar.search"):
        assert specs[read_like].minimum_risk == frozenset({RiskFlag.READ})
    for write_like in ("calendar.create", "calendar.update"):
        assert specs[write_like].minimum_risk == frozenset({RiskFlag.WRITE})
    assert specs["calendar.delete"].minimum_risk == frozenset(
        {RiskFlag.WRITE, RiskFlag.DESTRUCTIVE})


@pytest.mark.parametrize(
    "risk",
    [
        pytest.param([], id="empty"),
        pytest.param(["SENSITIVE"], id="only-sensitive"),
        pytest.param(["PRIVILEGED", "EXTERNAL_EFFECT"], id="no-read-or-write"),
        pytest.param(["DESTRUCTIVE"], id="destructive-alone"),
        pytest.param(["READ", "DESTRUCTIVE"], id="destructive-without-write"),
        pytest.param("READ", id="string-instead-of-list"),
        pytest.param(["READX"], id="unknown-flag"),
        pytest.param(["read"], id="lowercase-flag"),
        pytest.param([1], id="non-string-flag"),
        pytest.param(None, id="none"),
    ],
)
def test_spec_minimum_risk_rejected(risk):
    with pytest.raises(CapabilityContractError):
        CapabilitySpec.from_mapping(_spec_mapping(minimum_risk=risk))


@pytest.mark.parametrize(
    "risk",
    [["READ"], ["WRITE"], ["READ", "WRITE"], ["WRITE", "DESTRUCTIVE"],
     ["READ", "SENSITIVE"], ["WRITE", "EXTERNAL_EFFECT", "PRIVILEGED"]],
)
def test_spec_minimum_risk_accepted(risk):
    spec = CapabilitySpec.from_mapping(_spec_mapping(minimum_risk=risk))
    assert spec.minimum_risk == frozenset(RiskFlag[name] for name in risk)


@pytest.mark.parametrize("version", [0, -1, True, False, "1", 1.0, None])
def test_spec_contract_version_rejected(version):
    with pytest.raises(CapabilityContractError):
        CapabilitySpec.from_mapping(_spec_mapping(contract_version=version))


@pytest.mark.parametrize("version", [1, 2, 10])
def test_spec_contract_version_accepted(version):
    assert CapabilitySpec.from_mapping(_spec_mapping(contract_version=version)).contract_version \
        == version


@pytest.mark.parametrize("field", ["declared_risk", "extra", "provider_id", "created_by"])
def test_spec_unknown_field_rejected(field):
    with pytest.raises(CapabilityContractError, match="unknown field"):
        CapabilitySpec.from_mapping(_spec_mapping(**{field: "x"}))


@pytest.mark.parametrize("field", ["id", "contract_version", "minimum_risk"])
def test_spec_missing_required_field_rejected(field):
    data = _spec_mapping()
    del data[field]
    with pytest.raises(CapabilityContractError, match="missing field"):
        CapabilitySpec.from_mapping(data)


@pytest.mark.parametrize("data", [None, [], "spec", 5])
def test_spec_non_mapping_rejected(data):
    with pytest.raises(CapabilityContractError):
        CapabilitySpec.from_mapping(data)


@pytest.mark.parametrize(
    "refs",
    [
        pytest.param(["calendar_content"], id="lowercase"),
        pytest.param(["Calendar"], id="mixed-case"),
        pytest.param(["CALENDAR-CONTENT"], id="dash"),
        pytest.param(["CALENDAR__CONTENT"], id="double-underscore"),
        pytest.param(["CALENDAR_"], id="trailing-underscore"),
        pytest.param(["1ABC"], id="digit-first"),
        pytest.param([""], id="empty-entry"),
        pytest.param([5], id="non-string-entry"),
        pytest.param("CALENDAR_CONTENT", id="string-instead-of-list"),
        pytest.param(5, id="int"),
    ],
)
def test_spec_privacy_refs_rejected(refs):
    with pytest.raises(CapabilityContractError):
        CapabilitySpec.from_mapping(_spec_mapping(privacy_policy_refs=refs))


def test_spec_privacy_refs_accepted_and_optional():
    spec = CapabilitySpec.from_mapping(
        _spec_mapping(privacy_policy_refs=["A", "A1", "CALENDAR_CONTENT", "A_B2"]))
    assert spec.privacy_policy_refs == frozenset({"A", "A1", "CALENDAR_CONTENT", "A_B2"})
    data = _spec_mapping()
    del data["privacy_policy_refs"]
    assert CapabilitySpec.from_mapping(data).privacy_policy_refs == frozenset()


@pytest.mark.parametrize("capability", ["google.calendar.read", "Calendar.read", "calendar", "x.y"])
def test_spec_invalid_id_rejected(capability):
    with pytest.raises(CapabilityContractError):
        CapabilitySpec.from_mapping(_spec_mapping(id=capability))


def test_spec_is_frozen_and_normalized():
    spec = CapabilitySpec(
        id="calendar.read", contract_version=1, minimum_risk={RiskFlag.READ})
    assert spec.id == CapabilityId("calendar.read")
    assert isinstance(spec.minimum_risk, frozenset)
    with pytest.raises(FrozenInstanceError):
        spec.contract_version = 2
    with pytest.raises(FrozenInstanceError):
        spec.minimum_risk = frozenset({RiskFlag.WRITE})
