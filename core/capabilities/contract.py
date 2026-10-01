"""Immutable contract types: capability specs and provider descriptors.

A ``CapabilitySpec`` is owned by the core and fixes the minimum risk of a
capability. A ``ProviderDescriptor`` only declares what a provider offers and
which risk it adds on top. There is deliberately no field through which a
provider could state or lower the minimum risk.

Effective risk of a capability offered by a provider is the union of the spec's
minimum risk and the provider's additional risk for that capability.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from core.capabilities.vocabulary import (
    MERGE_FORBIDDEN_FLAGS,
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

_PROVIDER_ID = re.compile(r"[a-z][a-z0-9_]{1,63}")

_SPEC_REQUIRED = frozenset({"id", "contract_version", "minimum_risk"})
_SPEC_OPTIONAL = frozenset({"privacy_policy_refs"})


def _sorted_unique(values: Iterable[Any], label: str) -> tuple[Any, ...]:
    items = list(values)
    if len(set(items)) != len(items):
        raise CapabilityContractError(f"duplicate entries in {label}")
    return tuple(sorted(items))


@dataclass(frozen=True)
class CapabilitySpec:
    """Core-owned definition of a capability and its minimum risk."""

    id: CapabilityId
    contract_version: int
    minimum_risk: frozenset[RiskFlag]
    privacy_policy_refs: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", CapabilityId.parse(self.id))
        version = self.contract_version
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise CapabilityContractError("contract_version must be an integer >= 1")
        object.__setattr__(
            self, "minimum_risk",
            validate_risk_invariants(parse_risk_flags(self.minimum_risk)))
        object.__setattr__(
            self, "privacy_policy_refs", parse_privacy_refs(self.privacy_policy_refs))

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "CapabilitySpec":
        check_closed_fields(
            data, required=_SPEC_REQUIRED, optional=_SPEC_OPTIONAL, label="capability spec")
        return cls(
            id=data["id"],
            contract_version=data["contract_version"],
            minimum_risk=data["minimum_risk"],
            privacy_policy_refs=data.get("privacy_policy_refs", ()),
        )


@dataclass(frozen=True)
class ProviderDescriptor:
    """What a provider offers, where it runs and which risk it adds."""

    provider_id: str
    provides: tuple[CapabilityId, ...]
    execution_context: ExecutionContext
    additional_risk: Mapping[CapabilityId, frozenset[RiskFlag]] = field(default_factory=dict)
    egress_hosts: tuple[str, ...] = ()
    secret_refs: tuple[str, ...] = ()
    merge_semantics: MergeSemantics = MergeSemantics.NONE

    def __post_init__(self) -> None:
        provider_id = self.provider_id
        if not isinstance(provider_id, str) or not _PROVIDER_ID.fullmatch(provider_id):
            raise CapabilityContractError(
                "provider_id must be lowercase letters, digits and underscores, "
                "starting with a letter")

        if isinstance(self.provides, (str, bytes)) or not isinstance(self.provides, Iterable):
            raise CapabilityContractError("provides must be a collection of capability ids")
        provides = _sorted_unique((CapabilityId.parse(c) for c in self.provides), "provides")
        if not provides:
            raise CapabilityContractError("provides must not be empty")

        context = ExecutionContext.parse(self.execution_context)
        merge = MergeSemantics.parse(self.merge_semantics)

        if not isinstance(self.additional_risk, Mapping):
            raise CapabilityContractError("additional_risk must be a mapping")
        additional: dict[CapabilityId, frozenset[RiskFlag]] = {}
        for raw_id, raw_flags in self.additional_risk.items():
            capability = CapabilityId.parse(raw_id)
            if capability not in provides:
                raise CapabilityContractError(
                    f"additional_risk references '{capability}', which the provider does not offer")
            if capability in additional:
                raise CapabilityContractError(f"duplicate additional_risk entry for '{capability}'")
            additional[capability] = parse_risk_flags(raw_flags)

        if isinstance(self.egress_hosts, (str, bytes)) or not isinstance(self.egress_hosts, Iterable):
            raise CapabilityContractError("egress_hosts must be a collection of hosts")
        hosts = _sorted_unique((validate_egress_host(h) for h in self.egress_hosts), "egress_hosts")
        if context is ExecutionContext.LOCAL and hosts:
            raise CapabilityContractError("a LOCAL provider must not declare egress_hosts")
        if context in (ExecutionContext.NETWORK, ExecutionContext.CLOUD) and not hosts:
            raise CapabilityContractError(
                f"a {context.value} provider must declare at least one egress host")

        if isinstance(self.secret_refs, (str, bytes)) or not isinstance(self.secret_refs, Iterable):
            raise CapabilityContractError("secret_refs must be a collection of references")
        refs = _sorted_unique((validate_secret_ref(r) for r in self.secret_refs), "secret_refs")

        if merge is MergeSemantics.UNION:
            for capability, flags in additional.items():
                if flags & MERGE_FORBIDDEN_FLAGS:
                    raise CapabilityContractError(
                        f"UNION merge is not allowed: additional risk of '{capability}' "
                        "contains WRITE, DESTRUCTIVE or EXTERNAL_EFFECT")

        object.__setattr__(self, "provider_id", provider_id)
        object.__setattr__(self, "provides", provides)
        object.__setattr__(self, "execution_context", context)
        object.__setattr__(
            self, "additional_risk", MappingProxyType(dict(sorted(additional.items()))))
        object.__setattr__(self, "egress_hosts", hosts)
        object.__setattr__(self, "secret_refs", refs)
        object.__setattr__(self, "merge_semantics", merge)

    def additional_risk_for(self, capability: CapabilityId | str) -> frozenset[RiskFlag]:
        """Additional risk declared for one capability. Empty if none."""
        return self.additional_risk.get(CapabilityId.parse(capability), frozenset())


@runtime_checkable
class ProviderContract(Protocol):
    """Minimal provider contract: a provider can describe itself.

    Invocation, health and lifecycle are intentionally not part of it.
    """

    def describe(self) -> ProviderDescriptor:
        ...
