from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{43,512}$")


@dataclass(frozen=True, slots=True)
class ConnectorPackageSigningPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_attestation_schema: str
    maximum_attestation_age_hours: int
    required_assurance_level: AssuranceLevel
    signer_profile_id: str
    signer_workload_id: str
    key_id: str
    key_custodian_id: str
    algorithm: str
    envelope_schema: str
    receipt_schema: str
    signature_lifetime_hours: int
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
            self.required_attestation_schema,
            self.signer_profile_id,
            self.signer_workload_id,
            self.key_id,
            self.key_custodian_id,
            self.algorithm,
            self.envelope_schema,
            self.receipt_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "package signing policy identifier")
        if (
            self.version != 1
            or not 1 <= self.maximum_attestation_age_hours <= 87600
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not 1 <= self.signature_lifetime_hours <= 87600
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Package signing policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageSigningEnvelope:
    envelope_id: str
    schema_version: str
    version: int
    source_attestation_report_id: str
    source_attestation_report_digest: str
    source_approval_request_id: str
    source_approval_request_digest: str
    source_approval_decision_id: str
    source_approval_decision_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    publisher_id: str
    connector_id: str
    release_version: str
    provenance_digest: str
    publisher_claim_id: str
    publisher_claim_digest: str
    attestation_policy_id: str
    attestation_policy_digest: str
    signing_policy_id: str
    signing_policy_digest: str
    signing_policy_version: str
    signer_profile_id: str
    requested_by: str
    purpose: str
    created_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.envelope_id,
            self.schema_version,
            self.source_attestation_report_id,
            self.source_approval_request_id,
            self.source_approval_decision_id,
            self.organization_id,
            self.environment_id,
            self.publisher_id,
            self.connector_id,
            self.release_version,
            self.publisher_claim_id,
            self.attestation_policy_id,
            self.signing_policy_id,
            self.signing_policy_version,
            self.signer_profile_id,
            self.requested_by,
        ):
            validate_stable_identifier(value, "package signing envelope identifier")
        if any(
            _DIGEST.fullmatch(value) is None
            for value in (
                self.source_attestation_report_digest,
                self.source_approval_request_digest,
                self.source_approval_decision_digest,
                self.package_digest,
                self.provenance_digest,
                self.publisher_claim_digest,
                self.attestation_policy_digest,
                self.signing_policy_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Package signing envelope digest is invalid")
        if (
            self.version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.created_at.tzinfo is None
        ):
            raise ValueError("Package signing envelope contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageSignatureResult:
    signer_profile_id: str
    signer_workload_id: str
    key_id: str
    algorithm: str
    envelope_digest: str
    signature_value: str
    signature_digest: str
    issued_at: datetime
    expires_at: datetime
    signature_verified: bool

    def __post_init__(self) -> None:
        for value in (
            self.signer_profile_id,
            self.signer_workload_id,
            self.key_id,
            self.algorithm,
        ):
            validate_stable_identifier(value, "package signature identifier")
        if (
            _DIGEST.fullmatch(self.envelope_digest) is None
            or _SIGNATURE.fullmatch(self.signature_value) is None
            or _DIGEST.fullmatch(self.signature_digest) is None
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not self.signature_verified
        ):
            raise ValueError("Package signature result is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageSigningReceipt:
    receipt_id: str
    schema_version: str
    version: int
    envelope: ConnectorPackageSigningEnvelope
    signature: ConnectorPackageSignatureResult
    organization_id: str
    environment_id: str
    requested_by: str
    signing_policy_id: str
    signing_policy_digest: str
    signed_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    publisher_attested: bool = True
    package_signed: bool = True
    eligible_for_registry_governance: bool = True
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
            self.organization_id,
            self.environment_id,
            self.requested_by,
            self.signing_policy_id,
        ):
            validate_stable_identifier(value, "package signing receipt identifier")
        if (
            self.version != 1
            or any(
                _DIGEST.fullmatch(value) is None
                for value in (
                    self.signing_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not 8 <= len(self.idempotency_key) <= 128
            or self.signed_at.tzinfo is None
            or self.organization_id != self.envelope.organization_id
            or self.environment_id != self.envelope.environment_id
            or self.requested_by != self.envelope.requested_by
            or self.signing_policy_id != self.envelope.signing_policy_id
            or self.signing_policy_digest != self.envelope.signing_policy_digest
            or self.signature.envelope_digest != self.envelope.canonical_digest
            or not self.publisher_attested
            or not self.package_signed
            or not self.eligible_for_registry_governance
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
            raise ValueError("Package signing receipt violates the authority boundary")
