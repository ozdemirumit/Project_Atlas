from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class PublisherAttestationOutcome(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ConnectorPublisherClaimSnapshot:
    claim_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    publisher_id: str
    publisher_display_name: str
    connector_id: str
    release_version: str
    package_digest: str
    provenance_digest: str
    ownership_asserted: bool
    support_responsibility_asserted: bool
    support_contact_ref: str
    support_expires_at: datetime
    issued_by: str
    issued_at: datetime
    expires_at: datetime
    signature_verified: bool
    grants_no_runtime_authority: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.claim_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.publisher_id,
            self.connector_id,
            self.release_version,
            self.support_contact_ref,
            self.issued_by,
        ):
            validate_stable_identifier(value, "publisher claim identifier")
        if any(
            _DIGEST.fullmatch(value) is None
            for value in (
                self.package_digest,
                self.provenance_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Publisher claim digest is invalid")
        if (
            self.version != 1
            or not 2 <= len(self.publisher_display_name.strip()) <= 200
            or any(
                value.tzinfo is None
                for value in (
                    self.support_expires_at,
                    self.issued_at,
                    self.expires_at,
                )
            )
            or self.expires_at <= self.issued_at
            or not self.grants_no_runtime_authority
        ):
            raise ValueError("Publisher claim contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPublisherAttestationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_approval_schema: str
    required_claim_schema: str
    maximum_approval_age_hours: int
    maximum_claim_age_hours: int
    minimum_support_validity_days: int
    required_assurance_level: AssuranceLevel
    trusted_issuer_ids: tuple[str, ...]
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
            self.required_approval_schema,
            self.required_claim_schema,
            self.signed_by,
            *self.trusted_issuer_ids,
        ):
            validate_stable_identifier(value, "publisher attestation policy identifier")
        if (
            self.version != 1
            or not 1 <= self.maximum_approval_age_hours <= 87600
            or not 1 <= self.maximum_claim_age_hours <= 87600
            or not 0 <= self.minimum_support_validity_days <= 3650
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not self.trusted_issuer_ids
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Publisher attestation policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPublisherAttestationReport:
    report_id: str
    schema_version: str
    version: int
    source_approval_request_id: str
    source_approval_request_digest: str
    source_approval_decision_id: str
    source_approval_decision_digest: str
    organization_id: str
    environment_id: str
    verified_by: str
    purpose: str
    package_digest: str
    publisher_claim_id: str
    publisher_claim_digest: str
    publisher_id: str
    publisher_display_name: str
    connector_id: str
    release_version: str
    provenance_digest: str
    support_contact_ref: str
    support_expires_at: datetime
    claim_issued_by: str
    attestation_policy_id: str
    attestation_policy_digest: str
    attestation_policy_version: str
    check_codes: tuple[str, ...]
    outcome: PublisherAttestationOutcome
    reason_codes: tuple[str, ...]
    verified_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    publisher_attested: bool
    eligible_for_package_signing_governance: bool
    promotion_blocked: bool
    reused: bool = False
    package_signed: bool = False
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
            self.report_id,
            self.schema_version,
            self.source_approval_request_id,
            self.source_approval_decision_id,
            self.organization_id,
            self.environment_id,
            self.verified_by,
            self.publisher_claim_id,
            self.publisher_id,
            self.connector_id,
            self.release_version,
            self.support_contact_ref,
            self.claim_issued_by,
            self.attestation_policy_id,
            self.attestation_policy_version,
            *self.check_codes,
            *self.reason_codes,
        ):
            validate_stable_identifier(value, "publisher attestation report identifier")
        if any(
            _DIGEST.fullmatch(value) is None
            for value in (
                self.source_approval_request_digest,
                self.source_approval_decision_digest,
                self.package_digest,
                self.publisher_claim_digest,
                self.provenance_digest,
                self.attestation_policy_digest,
                self.canonical_digest,
                self.request_fingerprint,
            )
        ):
            raise ValueError("Publisher attestation report digest is invalid")
        passed = self.outcome is PublisherAttestationOutcome.VERIFIED
        if (
            self.version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 2 <= len(self.publisher_display_name.strip()) <= 200
            or not 8 <= len(self.idempotency_key) <= 128
            or self.support_expires_at.tzinfo is None
            or self.verified_at.tzinfo is None
            or not self.check_codes
            or self.publisher_attested != passed
            or self.eligible_for_package_signing_governance != passed
            or self.promotion_blocked == passed
            or any(
                (
                    self.package_signed,
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
            raise ValueError("Publisher attestation report violates the authority boundary")
