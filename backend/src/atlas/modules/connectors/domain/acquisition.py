from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_SAFE_FILENAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}\.zip$")


class PackageAcquisitionState(StrEnum):
    QUARANTINED = "quarantined"


class PackageAcquisitionSource(StrEnum):
    MCP_BUILDER_HANDOFF = "mcp_builder_handoff"


class PackageSignatureState(StrEnum):
    UNSIGNED = "unsigned"


class PublisherAttestationState(StrEnum):
    UNATTESTED = "unattested"


@dataclass(frozen=True, slots=True)
class AcquiredCapabilityEvidence:
    capability_id: str
    capability_class: str
    required_permission: str
    supported_product_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.capability_id, "capability id")
        if self.capability_class not in {"C0", "C1"}:
            raise ValueError("Acquired capability class is unsupported")
        if not self.required_permission.strip() or len(self.required_permission) > 300:
            raise ValueError("Acquired capability permission is invalid")
        if (
            not self.supported_product_versions
            or len(self.supported_product_versions) > 50
            or len(self.supported_product_versions) != len(set(self.supported_product_versions))
            or any(
                not value.strip() or len(value) > 500 for value in self.supported_product_versions
            )
        ):
            raise ValueError("Acquired capability product versions are invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageAcquisition:
    acquisition_id: str
    schema_version: str
    version: int
    state: PackageAcquisitionState
    source_type: PackageAcquisitionSource
    source_handoff_id: str
    source_handoff_digest: str
    source_project_id: str
    source_custodied_by: str
    source_domain_reviewed_by: str
    source_security_reviewed_by: str
    source_lab_operated_by: str
    organization_id: str
    environment_id: str
    acquired_by: str
    acquisition_profile: str
    archive_contract_version: str
    package_filename: str
    package_digest: str
    package_size_bytes: int
    publisher_identity: str
    signature_state: PackageSignatureState
    attestation_state: PublisherAttestationState
    capabilities: tuple[AcquiredCapabilityEvidence, ...]
    limitations: tuple[str, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    acquired_at: datetime
    package_acquired: bool = True
    integrity_verified: bool = True
    package_signed: bool = False
    publisher_attested: bool = False
    registry_validation_completed: bool = False
    connector_registered: bool = False
    connector_approved: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    target_configured: bool = False
    credentials_resolved: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.acquisition_id, "acquisition id"),
            (self.schema_version, "schema version"),
            (self.source_handoff_id, "source handoff id"),
            (self.source_project_id, "source project id"),
            (self.source_custodied_by, "source custodian id"),
            (self.source_domain_reviewed_by, "source domain reviewer id"),
            (self.source_security_reviewed_by, "source security reviewer id"),
            (self.source_lab_operated_by, "source lab operator id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.acquired_by, "registry intake operator id"),
            (self.acquisition_profile, "acquisition profile"),
            (self.archive_contract_version, "archive contract version"),
            (self.publisher_identity, "publisher identity"),
        ):
            validate_stable_identifier(value, name)
        if self.version != 1:
            raise ValueError("Package acquisition version is invalid")
        for value in (
            self.source_handoff_digest,
            self.package_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Package acquisition digest is invalid")
        if _SAFE_FILENAME.fullmatch(self.package_filename) is None:
            raise ValueError("Package acquisition filename is invalid")
        if not 1 <= self.package_size_bytes <= 25_000_000:
            raise ValueError("Package acquisition archive size is invalid")
        if self.acquired_by in {
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
        }:
            raise ValueError("Package acquisition violates separation of duties")
        if (
            self.state is not PackageAcquisitionState.QUARANTINED
            or self.source_type is not PackageAcquisitionSource.MCP_BUILDER_HANDOFF
            or self.signature_state is not PackageSignatureState.UNSIGNED
            or self.attestation_state is not PublisherAttestationState.UNATTESTED
            or self.publisher_identity != "unattested.generated"
        ):
            raise ValueError("Package acquisition trust state is invalid")
        if (
            not self.capabilities
            or len(self.capabilities) > 100
            or len({item.capability_id for item in self.capabilities}) != len(self.capabilities)
        ):
            raise ValueError("Package acquisition capabilities are invalid")
        if (
            not self.limitations
            or len(self.limitations) > 30
            or len(self.limitations) != len(set(self.limitations))
            or any(not value.strip() or len(value) > 500 for value in self.limitations)
        ):
            raise ValueError("Package acquisition limitations are invalid")
        if self.acquired_at.tzinfo is None or not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Package acquisition timestamp or idempotency key is invalid")
        if (
            not self.package_acquired
            or not self.integrity_verified
            or any(
                (
                    self.package_signed,
                    self.publisher_attested,
                    self.registry_validation_completed,
                    self.connector_registered,
                    self.connector_approved,
                    self.connector_installed,
                    self.connector_enabled,
                    self.target_configured,
                    self.credentials_resolved,
                    self.runtime_trust_granted,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Package acquisition violates the no-authority boundary")
