from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class ConnectorRegistryPublicationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_signing_receipt_schema: str
    required_signing_envelope_schema: str
    maximum_signing_age_hours: int
    required_assurance_level: AssuranceLevel
    required_signer_profile_id: str
    required_signer_workload_id: str
    required_key_id: str
    required_algorithm: str
    verifier_profile_id: str
    verifier_workload_id: str
    registry_profile_id: str
    publisher_workload_id: str
    registry_custodian_id: str
    artifact_reference_schema: str
    receipt_schema: str
    maximum_package_bytes: int
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
            self.required_signing_receipt_schema,
            self.required_signing_envelope_schema,
            self.required_signer_profile_id,
            self.required_signer_workload_id,
            self.required_key_id,
            self.required_algorithm,
            self.verifier_profile_id,
            self.verifier_workload_id,
            self.registry_profile_id,
            self.publisher_workload_id,
            self.registry_custodian_id,
            self.artifact_reference_schema,
            self.receipt_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "registry publication policy identifier")
        if (
            self.version != 1
            or not 1 <= self.maximum_signing_age_hours <= 87600
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not 1 <= self.maximum_package_bytes <= 25_000_000
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Registry publication policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageSignatureVerification:
    verifier_profile_id: str
    verifier_workload_id: str
    key_id: str
    algorithm: str
    envelope_digest: str
    signature_digest: str
    verified_at: datetime
    signature_valid: bool

    def __post_init__(self) -> None:
        for value in (
            self.verifier_profile_id,
            self.verifier_workload_id,
            self.key_id,
            self.algorithm,
        ):
            validate_stable_identifier(value, "signature verification identifier")
        if (
            _DIGEST.fullmatch(self.envelope_digest) is None
            or _DIGEST.fullmatch(self.signature_digest) is None
            or self.verified_at.tzinfo is None
            or not self.signature_valid
        ):
            raise ValueError("Package signature verification is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorInternalRegistryPublicationResult:
    registry_profile_id: str
    publisher_workload_id: str
    artifact_reference_schema: str
    artifact_reference: str
    package_digest: str
    package_size_bytes: int
    source_signing_receipt_digest: str
    publication_digest: str
    published_at: datetime
    integrity_verified: bool
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.registry_profile_id,
            self.publisher_workload_id,
            self.artifact_reference_schema,
            self.artifact_reference,
        ):
            validate_stable_identifier(value, "registry publication result identifier")
        if any(
            _DIGEST.fullmatch(value) is None
            for value in (
                self.package_digest,
                self.source_signing_receipt_digest,
                self.publication_digest,
            )
        ) or (
            not 1 <= self.package_size_bytes <= 25_000_000
            or self.published_at.tzinfo is None
            or not self.integrity_verified
        ):
            raise ValueError("Registry publication result is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorInternalRegistryPublicationReceipt:
    receipt_id: str
    schema_version: str
    version: int
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
    publication_policy_id: str
    publication_policy_digest: str
    publication_policy_version: str
    verification: ConnectorPackageSignatureVerification
    publication: ConnectorInternalRegistryPublicationResult
    requested_by: str
    purpose: str
    published_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    publisher_attested: bool = True
    package_signed: bool = True
    package_published: bool = True
    eligible_for_registration_governance: bool = True
    promotion_blocked: bool = False
    reused: bool = False
    connector_registered: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    target_configured: bool = False
    credentials_resolved: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.receipt_id,
            self.schema_version,
            self.source_signing_receipt_id,
            self.source_approval_request_id,
            self.source_final_validation_id,
            self.source_acquisition_id,
            self.organization_id,
            self.environment_id,
            self.publisher_id,
            self.connector_id,
            self.release_version,
            self.publication_policy_id,
            self.publication_policy_version,
            self.requested_by,
        ):
            validate_stable_identifier(value, "registry publication receipt identifier")
        if (
            self.version != 1
            or any(
                _DIGEST.fullmatch(value) is None
                for value in (
                    self.source_signing_receipt_digest,
                    self.source_approval_request_digest,
                    self.source_final_validation_digest,
                    self.source_acquisition_digest,
                    self.package_digest,
                    self.provenance_digest,
                    self.publication_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not 1 <= self.package_size_bytes <= 25_000_000
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.published_at.tzinfo is None
            or self.package_digest != self.publication.package_digest
            or self.package_size_bytes != self.publication.package_size_bytes
            or self.source_signing_receipt_digest != self.publication.source_signing_receipt_digest
            or not all(
                (
                    self.publisher_attested,
                    self.package_signed,
                    self.package_published,
                    self.eligible_for_registration_governance,
                )
            )
            or self.promotion_blocked
            or any(
                (
                    self.connector_registered,
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
            raise ValueError("Registry publication receipt violates the authority boundary")
