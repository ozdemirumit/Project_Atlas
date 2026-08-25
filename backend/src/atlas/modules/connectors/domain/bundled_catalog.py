from __future__ import annotations

import re
from dataclasses import dataclass

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class BundledConnectorDescriptor:
    catalog_item_id: str
    schema_version: str
    version: int
    connector_id: str
    display_name: str
    vendor_name: str
    release_version: str
    sdk_profile: str
    publisher_id: str
    support_group_id: str
    capability_ids: tuple[str, ...]
    capability_classes: tuple[str, ...]
    package_digest: str
    provenance_digest: str
    manifest_digest: str
    canonical_digest: str
    trusted_bundled: bool = True
    development_only: bool = True
    catalog_evidence_only: bool = True
    target_authority_granted: bool = False
    credential_authority_granted: bool = False
    capability_authority_granted: bool = False
    network_authority_granted: bool = False
    runtime_authority_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.catalog_item_id,
            self.schema_version,
            self.connector_id,
            self.release_version,
            self.sdk_profile,
            self.publisher_id,
            self.support_group_id,
            *self.capability_ids,
        ):
            validate_stable_identifier(value, "bundled connector descriptor identifier")
        if (
            self.version != 1
            or not 3 <= len(self.display_name.strip()) <= 200
            or not 2 <= len(self.vendor_name.strip()) <= 120
            or not self.capability_ids
            or not self.capability_classes
            or any(item not in {"C0", "C1"} for item in self.capability_classes)
            or any(
                _DIGEST.fullmatch(value) is None
                for value in (
                    self.package_digest,
                    self.provenance_digest,
                    self.manifest_digest,
                    self.canonical_digest,
                )
            )
            or not self.trusted_bundled
            or not self.development_only
            or not self.catalog_evidence_only
            or any(
                (
                    self.target_authority_granted,
                    self.credential_authority_granted,
                    self.capability_authority_granted,
                    self.network_authority_granted,
                    self.runtime_authority_granted,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Bundled connector descriptor violates the authority boundary")
