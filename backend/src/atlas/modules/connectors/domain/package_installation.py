from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class ConnectorPackageInstallationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_registration_record_schema: str
    maximum_registration_age_hours: int
    maximum_package_bytes: int
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
    installer_profile_id: str
    installer_workload_id: str
    installation_custodian_id: str
    installation_store_profile_id: str
    installation_artifact_reference_schema: str
    receipt_schema: str
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
            self.required_registration_record_schema,
            self.required_registry_profile_id,
            self.reader_workload_id,
            self.required_artifact_reference_schema,
            self.required_manifest_schema,
            self.required_manifest_status,
            self.required_sdk_profile,
            self.installer_profile_id,
            self.installer_workload_id,
            self.installation_custodian_id,
            self.installation_store_profile_id,
            self.installation_artifact_reference_schema,
            self.receipt_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "package installation policy identifier")
        if (
            self.version != 1
            or self.required_manifest_path != "atlas-connector.yaml"
            or self.allowed_capability_classes != ("C0", "C1")
            or not 1 <= self.maximum_registration_age_hours <= 87600
            or not 1 <= self.maximum_package_bytes <= 25_000_000
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
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
            raise ValueError("Package installation policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageInstallationResult:
    installer_profile_id: str
    installer_workload_id: str
    installation_custodian_id: str
    installation_store_profile_id: str
    artifact_reference_schema: str
    artifact_reference: str
    package_digest: str
    package_size_bytes: int
    stored_at: datetime

    def __post_init__(self) -> None:
        for value in (
            self.installer_profile_id,
            self.installer_workload_id,
            self.installation_custodian_id,
            self.installation_store_profile_id,
            self.artifact_reference_schema,
        ):
            validate_stable_identifier(value, "package installation result identifier")
        if (
            not self.artifact_reference.strip()
            or len(self.artifact_reference) > 1000
            or _DIGEST.fullmatch(self.package_digest) is None
            or not 1 <= self.package_size_bytes <= 25_000_000
            or self.stored_at.tzinfo is None
        ):
            raise ValueError("Package installation result is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageInstallationReceipt:
    receipt_id: str
    schema_version: str
    version: int
    source_registration_record_id: str
    source_registration_record_digest: str
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
    manifest_digest: str
    sdk_profile: str
    registry_profile_id: str
    registration_policy_id: str
    registration_policy_digest: str
    installation_policy_id: str
    installation_policy_digest: str
    installation_policy_version: str
    installation: ConnectorPackageInstallationResult
    installed_by: str
    purpose: str
    installed_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    package_published: bool = True
    connector_registered: bool = True
    package_installed: bool = True
    eligible_for_instance_governance: bool = True
    promotion_blocked: bool = False
    connector_enabled: bool = False
    instance_created: bool = False
    target_configured: bool = False
    credentials_resolved: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.receipt_id,
            self.schema_version,
            self.source_registration_record_id,
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
            self.sdk_profile,
            self.registry_profile_id,
            self.registration_policy_id,
            self.installation_policy_id,
            self.installation_policy_version,
            self.installed_by,
        ):
            validate_stable_identifier(value, "package installation receipt identifier")
        if (
            self.version != 1
            or any(
                _DIGEST.fullmatch(value) is None
                for value in (
                    self.source_registration_record_digest,
                    self.source_publication_receipt_digest,
                    self.source_signing_receipt_digest,
                    self.source_approval_request_digest,
                    self.source_final_validation_digest,
                    self.source_acquisition_digest,
                    self.package_digest,
                    self.provenance_digest,
                    self.manifest_digest,
                    self.registration_policy_digest,
                    self.installation_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not 1 <= self.package_size_bytes <= 25_000_000
            or self.package_digest != self.installation.package_digest
            or self.package_size_bytes != self.installation.package_size_bytes
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.installed_at.tzinfo is None
            or not all(
                (
                    self.package_published,
                    self.connector_registered,
                    self.package_installed,
                    self.eligible_for_instance_governance,
                )
            )
            or self.promotion_blocked
            or any(
                (
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
            raise ValueError("Package installation receipt violates the authority boundary")
