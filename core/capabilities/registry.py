"""In-memory registry of capability specs and provider manifests.

An explicitly created object. There is no module-level instance, no
persistence, no discovery and no I/O. The registry only stores and cross-checks
declarations; it does not resolve providers or invoke anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.capabilities.contract import CapabilitySpec
from core.capabilities.manifest import ProviderManifest
from core.capabilities.vocabulary import (
    MERGE_FORBIDDEN_FLAGS,
    CapabilityContractError,
    CapabilityId,
    MergeSemantics,
    RiskFlag,
    validate_risk_invariants,
)


class RegistryError(CapabilityContractError):
    """A registration or lookup violates a registry invariant."""


@dataclass(frozen=True)
class RegistrySnapshot:
    """Immutable, deterministically ordered view of the registry content."""

    specs: tuple[CapabilitySpec, ...]
    providers: tuple[ProviderManifest, ...]


class CapabilityRegistry:
    """Stores core specs and provider manifests and checks them against each other.

    Not thread-safe. Create and populate it explicitly.
    """

    def __init__(self) -> None:
        self._specs: dict[CapabilityId, CapabilitySpec] = {}
        self._providers: dict[str, ProviderManifest] = {}

    def register_spec(self, spec: CapabilitySpec) -> None:
        if not isinstance(spec, CapabilitySpec):
            raise RegistryError("register_spec expects a CapabilitySpec")
        if spec.id in self._specs:
            raise RegistryError(f"capability '{spec.id}' is already registered")
        self._specs[spec.id] = spec

    def register_provider(self, manifest: ProviderManifest) -> None:
        if not isinstance(manifest, ProviderManifest):
            raise RegistryError("register_provider expects a ProviderManifest")
        descriptor = manifest.describe()
        provider_id = descriptor.provider_id
        if provider_id in self._providers:
            raise RegistryError(f"provider '{provider_id}' is already registered")

        for capability in descriptor.provides:
            spec = self._specs.get(capability)
            if spec is None:
                raise RegistryError(
                    f"provider '{provider_id}' offers unknown capability '{capability}'")
            effective = spec.minimum_risk | descriptor.additional_risk_for(capability)
            try:
                validate_risk_invariants(effective)
            except CapabilityContractError as exc:
                raise RegistryError(
                    f"provider '{provider_id}', capability '{capability}': {exc}") from exc
            if descriptor.merge_semantics is MergeSemantics.UNION \
                    and effective & MERGE_FORBIDDEN_FLAGS:
                raise RegistryError(
                    f"provider '{provider_id}' declares UNION merge for '{capability}', "
                    "whose effective risk contains WRITE, DESTRUCTIVE or EXTERNAL_EFFECT")

        self._providers[provider_id] = manifest

    def get_spec(self, capability: CapabilityId | str) -> CapabilitySpec:
        capability_id = CapabilityId.parse(capability)
        try:
            return self._specs[capability_id]
        except KeyError:
            raise RegistryError(f"unknown capability '{capability_id}'") from None

    def providers_for(self, capability: CapabilityId | str) -> tuple[ProviderManifest, ...]:
        """Providers offering a capability, ordered by provider id.

        A lookup only. It neither ranks nor selects a provider.
        """
        capability_id = CapabilityId.parse(capability)
        if capability_id not in self._specs:
            raise RegistryError(f"unknown capability '{capability_id}'")
        return tuple(
            self._providers[provider_id]
            for provider_id in sorted(self._providers)
            if capability_id in self._providers[provider_id].describe().provides
        )

    def effective_risk(
        self, capability: CapabilityId | str, provider_id: str,
    ) -> frozenset[RiskFlag]:
        """Minimum risk of the spec united with the provider's additional risk."""
        spec = self.get_spec(capability)
        if not isinstance(provider_id, str):
            raise RegistryError("provider id must be a string")
        manifest = self._providers.get(provider_id)
        if manifest is None:
            raise RegistryError(f"unknown provider '{provider_id}'")
        descriptor = manifest.describe()
        if spec.id not in descriptor.provides:
            raise RegistryError(f"provider '{provider_id}' does not offer '{spec.id}'")
        return spec.minimum_risk | descriptor.additional_risk_for(spec.id)

    def snapshot(self) -> RegistrySnapshot:
        return RegistrySnapshot(
            specs=tuple(self._specs[key] for key in sorted(self._specs)),
            providers=tuple(self._providers[key] for key in sorted(self._providers)),
        )
