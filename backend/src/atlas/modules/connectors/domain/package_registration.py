from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


@dataclass(frozen=True, slots=True)
class ConnectorPackageRegistrationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_publication_receipt_schema: str
    maximum_publication_age_hours: int
    required_assurance_level: AssuranceLevel
    required_registry_profile_id: str
    reader_workload_id: str
    required_artifact_reference_schema: str
    required_manifest_path: str
    required_manifest_schema: str
    required_manifest_status: str
    required_sdk_profile: str
    allowed_capability_classes: tuple[str, ...]
    maximum_archive_entries: int
    maximum_manifest_bytes: int
    maximum_capabilities: int
    maximum_target_products: int
    maximum_network_destinations: int
    record_schema: str
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.required_publication_receipt_schema,
            self.required_registry_profile_id,
            self.reader_workload_id,
            self.required_artifact_reference_schema,
            self.required_manifest_schema,
            self.required_manifest_status,
            self.required_sdk_profile,
            self.record_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "package registration policy identifier")
        if (
            self.version != 1
            or self.required_manifest_path != "atlas-connector.yaml"
            or self.allowed_capability_classes != ("C0", "C1")
            or not 1 <= self.maximum_publication_age_hours <= 87600
            or self.required_assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
            or not 1 <= self.maximum_archive_entries <= 500
            or not 256 <= self.maximum_manifest_bytes <= 1_000_000
            or not 1 <= self.maximum_capabilities <= 500
            or not 1 <= self.maximum_target_products <= 100
            or not 0 <= self.maximum_network_destinations <= 100
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Package registration policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorRegisteredCapability:
    capability_id: str
    capability_class: str
    required_permission: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.capability_id, "registered capability identifier")
        validate_stable_identifier(self.required_permission, "registered capability permission")
        if self.capability_class not in {"C0", "C1"}:
            raise ValueError("Registered capability class is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorRegisteredManifestSnapshot:
    schema_version: str
    connector_id: str
    manifest_version: str
    release_version: str
    source_status: str
    sdk_profile: str
    target_products: tuple[str, ...]
    network_destinations: tuple[str, ...]
    configuration_key_count: int
    secret_reference_count: int
    capabilities: tuple[ConnectorRegisteredCapability, ...]
    manifest_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.schema_version,
            self.connector_id,
            self.release_version,
            self.source_status,
            self.sdk_profile,
        ):
            validate_stable_identifier(value, "registered manifest identifier")
        if _SEMVER.fullmatch(self.manifest_version) is None:
            raise ValueError("Registered manifest version is invalid")
        if self.release_version != f"version.{self.manifest_version}":
            raise ValueError("Registered manifest release binding is invalid")
        if (
            _DIGEST.fullmatch(self.manifest_digest) is None
            or not self.target_products
            or len(self.target_products) != len(set(self.target_products))
            or len(self.network_destinations) != len(set(self.network_destinations))
            or min(self.configuration_key_count, self.secret_reference_count) < 0
            or not self.capabilities
            or len({item.capability_id for item in self.capabilities}) != len(self.capabilities)
        ):
            raise ValueError("Registered manifest evidence is invalid")
        if any(not item.strip() or len(item) > 200 for item in self.target_products):
            raise ValueError("Registered target product evidence is invalid")
        if any(not item.strip() or len(item) > 253 for item in self.network_destinations):
            raise ValueError("Registered network destination evidence is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageRegistrationRecord:
    record_id: str
    schema_version: str
    version: int
    source_publication_receipt_id: str
    source_publication_receipt_digest: str
    source_signing_receipt_id: str
    source_signing_receipt_digest: str
    source_approval_request_id: str
    source_approval_request_digest: str
    source_final_validation_id: str
    source_final_validation_digest: str
    source_acquisition_id: str
    source_acquisition_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    package_size_bytes: int
    publisher_id: str
    connector_id: str
    release_version: str
    provenance_digest: str
    registry_profile_id: str
    reader_workload_id: str
    registration_policy_id: str
    registration_policy_digest: str
    registration_policy_version: str
    manifest: ConnectorRegisteredManifestSnapshot
    registered_by: str
    purpose: str
    registered_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    package_published: bool = True
    connector_registered: bool = True
    eligible_for_installation_governance: bool = True
    promotion_blocked: bool = False
    reused: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    instance_created: bool = False
    target_configured: bool = False
    credentials_resolved: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.record_id,
            self.schema_version,
            self.source_publication_receipt_id,
            self.source_signing_receipt_id,
            self.source_approval_request_id,
            self.source_final_validation_id,
            self.source_acquisition_id,
            self.organization_id,
            self.environment_id,
            self.publisher_id,
            self.connector_id,
            self.release_version,
            self.registry_profile_id,
            self.reader_workload_id,
            self.registration_policy_id,
            self.registration_policy_version,
            self.registered_by,
        ):
            validate_stable_identifier(value, "package registration record identifier")
        if (
            self.version != 1
            or any(
                _DIGEST.fullmatch(value) is None
                for value in (
                    self.source_publication_receipt_digest,
                    self.source_signing_receipt_digest,
                    self.source_approval_request_digest,
                    self.source_final_validation_digest,
                    self.source_acquisition_digest,
                    self.package_digest,
                    self.provenance_digest,
                    self.registration_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not 1 <= self.package_size_bytes <= 25_000_000
            or self.connector_id != self.manifest.connector_id
            or self.release_version != self.manifest.release_version
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.registered_at.tzinfo is None
            or not all(
                (
                    self.package_published,
                    self.connector_registered,
                    self.eligible_for_installation_governance,
                )
            )
            or self.promotion_blocked
            or any(
                (
                    self.connector_installed,
                    self.connector_enabled,
                    self.instance_created,
                    self.target_configured,
                    self.credentials_resolved,
                    self.runtime_trust_granted,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Package registration record violates the authority boundary")
