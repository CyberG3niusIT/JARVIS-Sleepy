"""Declarative provider manifest with a closed schema.

A manifest only declares. It carries no credentials, no secret values, no
runtime state, no code and no build or authorship metadata. Unknown fields are
rejected, which also covers any field not listed below.

Validation is declarative: schema, ids, versions, risk flags, execution
context, host and secret-reference syntax, duplicates and contradictions within
the manifest. It says nothing about what provider code actually does.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.capabilities.contract import ProviderDescriptor
from core.capabilities.vocabulary import (
    CapabilityContractError,
    ExecutionContext,
    MergeSemantics,
    check_closed_fields,
)

MANIFEST_SCHEMA_VERSION = 1

_PROVIDER_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")

_REQUIRED = frozenset({
    "schema_version", "provider_id", "provider_version", "provides", "execution_context",
})
_OPTIONAL = frozenset({
    "additional_risk", "egress_hosts", "secret_refs", "merge_semantics",
})


class ManifestError(CapabilityContractError):
    """A manifest violates the declarative schema or its own invariants."""


def _string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) for v in value):
        raise ManifestError(f"manifest field '{name}' must be a list of strings")
    return list(value)


@dataclass(frozen=True)
class ProviderManifest:
    """Validated manifest: schema and provider version plus the descriptor."""

    schema_version: int
    provider_version: str
    descriptor: ProviderDescriptor

    def __post_init__(self) -> None:
        version = self.schema_version
        if isinstance(version, bool) or not isinstance(version, int) \
                or version != MANIFEST_SCHEMA_VERSION:
            raise ManifestError(
                f"unsupported manifest schema_version {version!r}; "
                f"expected {MANIFEST_SCHEMA_VERSION}")
        provider_version = self.provider_version
        if not isinstance(provider_version, str) or not _PROVIDER_VERSION.fullmatch(provider_version):
            raise ManifestError("provider_version must look like MAJOR.MINOR.PATCH")
        if not isinstance(self.descriptor, ProviderDescriptor):
            raise ManifestError("descriptor must be a ProviderDescriptor")

    @property
    def provider_id(self) -> str:
        return self.descriptor.provider_id

    def describe(self) -> ProviderDescriptor:
        return self.descriptor

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ProviderManifest":
        try:
            check_closed_fields(
                data, required=_REQUIRED, optional=_OPTIONAL, label="manifest")

            additional_raw = data.get("additional_risk", {})
            if not isinstance(additional_raw, Mapping):
                raise ManifestError("manifest field 'additional_risk' must be a mapping")
            additional = {
                key: _string_list(flags, "additional_risk")
                for key, flags in additional_raw.items()
            }

            descriptor = ProviderDescriptor(
                provider_id=data["provider_id"],
                provides=_string_list(data["provides"], "provides"),
                execution_context=ExecutionContext.parse(data["execution_context"]),
                additional_risk=additional,
                egress_hosts=_string_list(data.get("egress_hosts", []), "egress_hosts"),
                secret_refs=_string_list(data.get("secret_refs", []), "secret_refs"),
                merge_semantics=MergeSemantics.parse(data.get("merge_semantics", "NONE")),
            )
            return cls(
                schema_version=data["schema_version"],
                provider_version=data["provider_version"],
                descriptor=descriptor,
            )
        except ManifestError:
            raise
        except CapabilityContractError as exc:
            raise ManifestError(str(exc)) from exc
