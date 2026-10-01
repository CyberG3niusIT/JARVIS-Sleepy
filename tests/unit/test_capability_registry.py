"""Unit tests for the in-memory capability registry.

Covers registration rules, atomic failure, effective risk (minimum risk united
with the additive provider risk), lookup order, snapshots and isolation between
registry instances. The registry is only ever created inside fixtures.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import core.capabilities.registry as registry_module
from core.capabilities.contract import CapabilitySpec
from core.capabilities.manifest import ProviderManifest
from core.capabilities.registry import (
    CapabilityRegistry,
    RegistryError,
    RegistrySnapshot,
)
from core.capabilities.vocabulary import (
    CapabilityContractError,
    CapabilityId,
    RiskFlag,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "capabilities"


def _load_json(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


# Plain data only; no registry instance lives at module level.
SPEC_DATA = _load_json("calendar_specs.json")
CAPABILITY_IDS = [entry["id"] for entry in SPEC_DATA]
EXPECTED_SORTED_IDS = sorted(CAPABILITY_IDS)


def _manifest_data(**overrides):
    data = {
        "schema_version": 1,
        "provider_version": "1.0.0",
        "provider_id": "test_provider",
        "provides": ["calendar.read"],
        "execution_context": "LOCAL",
    }
    data.update(overrides)
    return data


def _provider(provider_id: str, provides, **overrides) -> ProviderManifest:
    return ProviderManifest.from_mapping(
        _manifest_data(provider_id=provider_id, provides=list(provides), **overrides))


def _flags(names) -> frozenset:
    return frozenset(RiskFlag[name] for name in names)


@pytest.fixture
def specs():
    return [CapabilitySpec.from_mapping(entry) for entry in SPEC_DATA]


@pytest.fixture
def registry(specs):
    instance = CapabilityRegistry()
    for spec in specs:
        instance.register_spec(spec)
    return instance


@pytest.fixture
def fixture_manifest():
    return ProviderManifest.from_mapping(_load_json("example_provider_manifest.json"))


@pytest.fixture
def loaded_registry(registry, fixture_manifest):
    registry.register_provider(fixture_manifest)
    return registry


# ---------------------------------------------------------------------------
# Start set
# ---------------------------------------------------------------------------

def test_calendar_start_set_only_calendar_capabilities(specs):
    assert specs
    assert all(str(spec.id).startswith("calendar.") for spec in specs)
    assert sorted(str(spec.id) for spec in specs) == [
        "calendar.create", "calendar.delete", "calendar.list",
        "calendar.read", "calendar.search", "calendar.update",
    ]
    assert len({spec.id for spec in specs}) == len(specs)


def test_registry_holds_the_calendar_start_set(registry):
    snapshot = registry.snapshot()
    assert [str(spec.id) for spec in snapshot.specs] == EXPECTED_SORTED_IDS
    assert snapshot.providers == ()


# ---------------------------------------------------------------------------
# Spec registration
# ---------------------------------------------------------------------------

def test_duplicate_spec_rejected(registry, specs):
    with pytest.raises(RegistryError, match="already registered"):
        registry.register_spec(specs[0])


def test_spec_with_same_id_but_other_content_rejected(registry):
    other = CapabilitySpec(
        id="calendar.read", contract_version=2, minimum_risk={RiskFlag.READ})
    with pytest.raises(RegistryError):
        registry.register_spec(other)
    assert registry.get_spec("calendar.read").contract_version == 1


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param({"id": "calendar.read"}, id="dict"),
        pytest.param("calendar.read", id="string"),
        pytest.param(None, id="none"),
        pytest.param(CapabilityId("calendar.read"), id="capability-id"),
        pytest.param(5, id="int"),
    ],
)
def test_register_spec_wrong_type_rejected(registry, bad):
    before = registry.snapshot()
    with pytest.raises(RegistryError):
        registry.register_spec(bad)
    assert registry.snapshot() == before


def test_register_spec_rejects_manifest(registry, fixture_manifest):
    with pytest.raises(RegistryError):
        registry.register_spec(fixture_manifest)


# ---------------------------------------------------------------------------
# Provider registration
# ---------------------------------------------------------------------------

def test_fixture_manifest_registers(loaded_registry):
    snapshot = loaded_registry.snapshot()
    assert [m.provider_id for m in snapshot.providers] == ["example_local_calendar"]


def test_duplicate_provider_rejected_and_state_kept(loaded_registry, fixture_manifest):
    before = loaded_registry.snapshot()
    with pytest.raises(RegistryError, match="already registered"):
        loaded_registry.register_provider(fixture_manifest)
    assert loaded_registry.snapshot() == before
    assert len(loaded_registry.snapshot().providers) == 1


def test_duplicate_provider_id_with_other_content_rejected(loaded_registry):
    impostor = _provider("example_local_calendar", ["calendar.create"])
    with pytest.raises(RegistryError):
        loaded_registry.register_provider(impostor)
    assert loaded_registry.providers_for("calendar.create") == ()


class _DescribeOnly:
    """Satisfies the describe() protocol but is not a ProviderManifest."""

    def __init__(self, manifest):
        self._manifest = manifest

    def describe(self):
        return self._manifest.describe()


@pytest.mark.parametrize(
    "make_bad",
    [
        pytest.param(lambda m, s: {"provider_id": "x"}, id="dict"),
        pytest.param(lambda m, s: None, id="none"),
        pytest.param(lambda m, s: "example_local_calendar", id="string"),
        pytest.param(lambda m, s: m.describe(), id="descriptor"),
        pytest.param(lambda m, s: s[0], id="spec"),
        pytest.param(lambda m, s: _DescribeOnly(m), id="describe-only-object"),
    ],
)
def test_register_provider_wrong_type_rejected(registry, fixture_manifest, specs, make_bad):
    before = registry.snapshot()
    with pytest.raises(RegistryError):
        registry.register_provider(make_bad(fixture_manifest, specs))
    assert registry.snapshot() == before


def test_provider_with_unknown_capability_rejected_and_registry_unchanged(registry):
    manifest = _provider("weather_provider", ["calendar.read", "weather.read"])
    before = registry.snapshot()
    with pytest.raises(RegistryError, match="unknown capability"):
        registry.register_provider(manifest)
    assert registry.snapshot() == before
    assert registry.snapshot().providers == ()
    assert registry.providers_for("calendar.read") == ()
    with pytest.raises(RegistryError):
        registry.effective_risk("calendar.read", "weather_provider")


def test_unknown_capability_listed_first_does_not_leave_partial_state(registry):
    manifest = _provider("weather_provider", ["calendar.list", "weather.read"])
    with pytest.raises(RegistryError):
        registry.register_provider(manifest)
    assert registry.providers_for("calendar.list") == ()


def test_provider_rejected_when_registry_has_no_specs():
    empty = CapabilityRegistry()
    with pytest.raises(RegistryError):
        empty.register_provider(_provider("any_provider", ["calendar.read"]))
    assert empty.snapshot().providers == ()


def test_provider_rejected_if_only_part_of_its_capabilities_have_specs(fixture_manifest):
    partial = CapabilityRegistry()
    partial.register_spec(CapabilitySpec.from_mapping(
        next(entry for entry in SPEC_DATA if entry["id"] == "calendar.read")))
    with pytest.raises(RegistryError):
        partial.register_provider(fixture_manifest)
    assert partial.snapshot().providers == ()


# ---------------------------------------------------------------------------
# Effective risk
# ---------------------------------------------------------------------------

def test_effective_risk_of_fixture_provider(loaded_registry):
    assert loaded_registry.effective_risk("calendar.read", "example_local_calendar") == frozenset(
        {RiskFlag.READ, RiskFlag.SENSITIVE})
    assert loaded_registry.effective_risk("calendar.list", "example_local_calendar") == frozenset(
        {RiskFlag.READ})
    assert loaded_registry.effective_risk("calendar.search", "example_local_calendar") == \
        frozenset({RiskFlag.READ})


def test_effective_risk_accepts_capability_id_objects(loaded_registry):
    assert loaded_registry.effective_risk(
        CapabilityId("calendar.read"), "example_local_calendar") == frozenset(
            {RiskFlag.READ, RiskFlag.SENSITIVE})


@pytest.mark.parametrize("capability", CAPABILITY_IDS)
@pytest.mark.parametrize(
    "extra",
    [[], ["SENSITIVE"], ["PRIVILEGED"], ["EXTERNAL_EFFECT"], ["SENSITIVE", "PRIVILEGED"]],
)
def test_effective_risk_is_union_and_superset_of_minimum(registry, capability, extra):
    registry.register_provider(
        _provider("risk_provider", [capability], additional_risk={capability: extra}))
    spec = registry.get_spec(capability)
    effective = registry.effective_risk(capability, "risk_provider")
    assert effective == spec.minimum_risk | _flags(extra)
    assert spec.minimum_risk <= effective


@pytest.mark.parametrize("capability", CAPABILITY_IDS)
def test_provider_without_additional_risk_gets_exactly_minimum_risk(registry, capability):
    registry.register_provider(_provider("plain_provider", [capability]))
    assert registry.effective_risk(capability, "plain_provider") == \
        registry.get_spec(capability).minimum_risk


def test_empty_additional_risk_entry_does_not_lower_minimum(registry):
    registry.register_provider(_provider(
        "empty_risk_provider", ["calendar.delete"],
        additional_risk={"calendar.delete": []}))
    assert registry.effective_risk("calendar.delete", "empty_risk_provider") == frozenset(
        {RiskFlag.WRITE, RiskFlag.DESTRUCTIVE})


def test_additional_read_on_write_capability_only_adds(registry):
    registry.register_provider(_provider(
        "reading_writer", ["calendar.create"],
        additional_risk={"calendar.create": ["READ"]}))
    assert registry.effective_risk("calendar.create", "reading_writer") == frozenset(
        {RiskFlag.WRITE, RiskFlag.READ})


@pytest.mark.parametrize("field", ["minimum_risk", "declared_risk"])
def test_provider_cannot_state_a_risk_of_its_own(registry, field):
    data = _manifest_data(provider_id="sneaky_provider", **{field: ["READ"]})
    with pytest.raises(CapabilityContractError):
        ProviderManifest.from_mapping(data)
    assert registry.snapshot().providers == ()


def test_provider_adding_destructive_to_read_only_capability_rejected(registry):
    manifest = _provider(
        "destructive_reader", ["calendar.read"],
        additional_risk={"calendar.read": ["DESTRUCTIVE"]})
    before = registry.snapshot()
    with pytest.raises(RegistryError, match="DESTRUCTIVE requires WRITE"):
        registry.register_provider(manifest)
    assert registry.snapshot() == before
    assert registry.providers_for("calendar.read") == ()


def test_provider_adding_write_and_destructive_to_read_capability_is_additive(registry):
    registry.register_provider(_provider(
        "escalating_reader", ["calendar.read"],
        additional_risk={"calendar.read": ["WRITE", "DESTRUCTIVE"]}))
    assert registry.effective_risk("calendar.read", "escalating_reader") == frozenset(
        {RiskFlag.READ, RiskFlag.WRITE, RiskFlag.DESTRUCTIVE})


def test_effective_risk_is_a_frozenset(loaded_registry):
    result = loaded_registry.effective_risk("calendar.read", "example_local_calendar")
    assert isinstance(result, frozenset)


# ---------------------------------------------------------------------------
# UNION merge against core minimum risk
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("capability", ["calendar.create", "calendar.update", "calendar.delete"])
def test_union_rejected_for_capability_with_write_in_minimum_risk(registry, capability):
    manifest = _provider("union_writer", [capability], merge_semantics="UNION")
    # The manifest alone is valid: additional risk is empty.
    assert manifest.describe().additional_risk_for(capability) == frozenset()
    before = registry.snapshot()
    with pytest.raises(RegistryError, match="UNION"):
        registry.register_provider(manifest)
    assert registry.snapshot() == before
    assert registry.providers_for(capability) == ()


@pytest.mark.parametrize("capability", ["calendar.create", "calendar.update", "calendar.delete"])
def test_merge_none_may_offer_write_capabilities(registry, capability):
    registry.register_provider(_provider("plain_writer", [capability], merge_semantics="NONE"))
    assert [m.provider_id for m in registry.providers_for(capability)] == ["plain_writer"]


@pytest.mark.parametrize("capability", ["calendar.list", "calendar.read", "calendar.search"])
def test_union_allowed_for_read_only_capabilities(registry, capability):
    registry.register_provider(_provider("union_reader", [capability], merge_semantics="UNION"))
    assert len(registry.providers_for(capability)) == 1


def test_union_provider_mixing_read_and_write_capabilities_rejected_atomically(registry):
    manifest = _provider(
        "mixed_union", ["calendar.read", "calendar.create"], merge_semantics="UNION")
    with pytest.raises(RegistryError, match="UNION"):
        registry.register_provider(manifest)
    assert registry.providers_for("calendar.read") == ()
    assert registry.providers_for("calendar.create") == ()


# ---------------------------------------------------------------------------
# providers_for
# ---------------------------------------------------------------------------

PROVIDER_IDS = ["zeta_calendar", "alpha_calendar", "example_local_calendar"]


@pytest.mark.parametrize("order", list(itertools.permutations(PROVIDER_IDS)))
def test_providers_for_is_sorted_by_provider_id(registry, order):
    manifests = {provider_id: _provider(provider_id, ["calendar.read"]) for provider_id in order}
    for provider_id in order:
        registry.register_provider(manifests[provider_id])
    result = registry.providers_for("calendar.read")
    assert isinstance(result, tuple)
    assert [m.provider_id for m in result] == sorted(PROVIDER_IDS)
    for manifest in result:
        assert manifest is manifests[manifest.provider_id]


def test_providers_for_only_returns_providers_offering_the_capability(registry):
    registry.register_provider(_provider("lister_only", ["calendar.list"]))
    registry.register_provider(_provider("reader_only", ["calendar.read"]))
    assert [m.provider_id for m in registry.providers_for("calendar.read")] == ["reader_only"]
    assert [m.provider_id for m in registry.providers_for("calendar.list")] == ["lister_only"]


def test_providers_for_known_capability_without_provider_is_empty_tuple(registry):
    assert registry.providers_for("calendar.update") == ()
    assert isinstance(registry.providers_for("calendar.update"), tuple)


def test_providers_for_fixture_provider(loaded_registry):
    assert [m.provider_id for m in loaded_registry.providers_for("calendar.search")] == [
        "example_local_calendar"]
    assert loaded_registry.providers_for("calendar.create") == ()


@pytest.mark.parametrize("capability", ["weather.read", CapabilityId("weather.read")])
def test_providers_for_unknown_capability_rejected(registry, capability):
    with pytest.raises(RegistryError, match="unknown capability"):
        registry.providers_for(capability)


@pytest.mark.parametrize("capability", ["Not A Capability", "calendar", "", 5, None])
def test_providers_for_invalid_capability_string_is_contract_error(registry, capability):
    with pytest.raises(CapabilityContractError) as excinfo:
        registry.providers_for(capability)
    assert not isinstance(excinfo.value, RegistryError)


def test_registry_offers_lookup_only_no_selection_or_ranking(registry):
    public = [name for name in dir(registry) if not name.startswith("_")]
    forbidden = ("select", "rank", "resolve", "choose", "best", "pick", "route")
    assert not [name for name in public if any(word in name for word in forbidden)]


# ---------------------------------------------------------------------------
# get_spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("capability", CAPABILITY_IDS)
def test_get_spec_accepts_string_and_capability_id(registry, capability):
    by_string = registry.get_spec(capability)
    by_id = registry.get_spec(CapabilityId(capability))
    assert by_string is by_id
    assert str(by_string.id) == capability


@pytest.mark.parametrize("capability", ["weather.read", CapabilityId("weather.read")])
def test_get_spec_unknown_rejected(registry, capability):
    with pytest.raises(RegistryError, match="unknown capability"):
        registry.get_spec(capability)


@pytest.mark.parametrize("capability", ["Not A Capability", "calendar.explode", 5, None])
def test_get_spec_invalid_value_is_contract_error(registry, capability):
    with pytest.raises(CapabilityContractError) as excinfo:
        registry.get_spec(capability)
    assert not isinstance(excinfo.value, RegistryError)


# ---------------------------------------------------------------------------
# effective_risk error paths
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider_id", ["missing_provider", "", "Example_Local_Calendar", 5])
def test_effective_risk_unknown_provider_rejected(loaded_registry, provider_id):
    with pytest.raises(RegistryError, match="unknown provider|must be a string"):
        loaded_registry.effective_risk("calendar.read", provider_id)


@pytest.mark.parametrize("capability", ["calendar.create", "calendar.update", "calendar.delete"])
def test_effective_risk_provider_not_offering_capability_rejected(loaded_registry, capability):
    with pytest.raises(RegistryError, match="does not offer"):
        loaded_registry.effective_risk(capability, "example_local_calendar")


def test_effective_risk_unknown_capability_rejected(loaded_registry):
    with pytest.raises(RegistryError, match="unknown capability"):
        loaded_registry.effective_risk("weather.read", "example_local_calendar")


def test_effective_risk_invalid_capability_is_contract_error(loaded_registry):
    with pytest.raises(CapabilityContractError) as excinfo:
        loaded_registry.effective_risk("Not A Capability", "example_local_calendar")
    assert not isinstance(excinfo.value, RegistryError)


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def test_snapshot_is_frozen_and_uses_tuples(loaded_registry):
    snapshot = loaded_registry.snapshot()
    assert isinstance(snapshot, RegistrySnapshot)
    assert isinstance(snapshot.specs, tuple)
    assert isinstance(snapshot.providers, tuple)
    with pytest.raises(FrozenInstanceError):
        snapshot.specs = ()
    with pytest.raises(FrozenInstanceError):
        snapshot.providers = ()
    with pytest.raises(TypeError):
        snapshot.specs[0] = snapshot.specs[1]


def test_snapshot_specs_sorted_by_id_regardless_of_registration_order(specs):
    ids_per_order = []
    for order in (list(specs), list(reversed(specs)), specs[1:] + specs[:1]):
        instance = CapabilityRegistry()
        for spec in order:
            instance.register_spec(spec)
        ids_per_order.append([str(spec.id) for spec in instance.snapshot().specs])
    assert all(ids == EXPECTED_SORTED_IDS for ids in ids_per_order)


@pytest.mark.parametrize("order", list(itertools.permutations(PROVIDER_IDS)))
def test_snapshot_providers_sorted_by_provider_id(registry, order):
    for provider_id in order:
        registry.register_provider(_provider(provider_id, ["calendar.read"]))
    assert [m.provider_id for m in registry.snapshot().providers] == sorted(PROVIDER_IDS)


def test_earlier_snapshot_is_not_changed_by_later_registration(registry, fixture_manifest):
    early = registry.snapshot()
    early_spec_ids = [str(spec.id) for spec in early.specs]
    registry.register_provider(fixture_manifest)
    registry.register_provider(_provider("second_provider", ["calendar.create"]))
    assert early.providers == ()
    assert [str(spec.id) for spec in early.specs] == early_spec_ids
    late = registry.snapshot()
    assert [m.provider_id for m in late.providers] == ["example_local_calendar", "second_provider"]


def test_snapshot_of_empty_registry():
    snapshot = CapabilityRegistry().snapshot()
    assert snapshot.specs == ()
    assert snapshot.providers == ()


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------

def test_two_registries_share_no_state(specs, fixture_manifest):
    first = CapabilityRegistry()
    second = CapabilityRegistry()
    for spec in specs:
        first.register_spec(spec)
    first.register_provider(fixture_manifest)

    assert second.snapshot().specs == ()
    assert second.snapshot().providers == ()
    with pytest.raises(RegistryError):
        second.get_spec("calendar.read")
    with pytest.raises(RegistryError):
        second.providers_for("calendar.read")

    # The same ids can be registered independently in the second instance.
    for spec in specs:
        second.register_spec(spec)
    second.register_provider(fixture_manifest)
    assert len(first.snapshot().providers) == len(second.snapshot().providers) == 1


def test_failed_registration_in_one_registry_does_not_affect_another(specs):
    first = CapabilityRegistry()
    second = CapabilityRegistry()
    for instance in (first, second):
        for spec in specs:
            instance.register_spec(spec)
    with pytest.raises(RegistryError):
        first.register_provider(_provider("weather_provider", ["weather.read"]))
    second.register_provider(_provider("calendar_reader", ["calendar.read"]))
    assert first.snapshot().providers == ()
    assert [m.provider_id for m in second.snapshot().providers] == ["calendar_reader"]


def test_no_module_level_registry_instance():
    instances = [
        name for name, value in vars(registry_module).items()
        if isinstance(value, CapabilityRegistry)
    ]
    assert instances == []
