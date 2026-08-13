from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

FINAL_ACCEPTED = "recommendation-disposition.accepted"
FINAL_REJECTED = "recommendation-disposition.rejected"
FINAL_DISPOSITIONS = frozenset((FINAL_ACCEPTED, FINAL_REJECTED))
FINAL_ACCEPTED_STATE = "recommendation_final_accepted"
FINAL_REJECTED_STATE = "recommendation_final_rejected"
TRACKS = frozenset(("review-track.technical", "review-track.service-impact"))
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "final recommendation disposition identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class FinalRecommendationDispositionPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_decision_schema: str
    required_decision_state: str
    required_request_schema: str
    required_request_state: str
    required_readiness_schema: str
    required_readiness_state: str
    required_promotion_schema: str
    required_promotion_state: str
    allowed_dispositions: tuple[str, ...]
    accepted_basis_codes: tuple[str, ...]
    rejected_basis_codes: tuple[str, ...]
    forbidden_approver_role_ids: tuple[str, ...]
    maximum_basis_codes: int
    maximum_authentication_age_minutes: int
    maximum_attestation_delay_seconds: int
    required_assurance_level: AssuranceLevel
    source_consumer_subject_digest_salt_digest: str
    approver_subject_digest_salt_digest: str
    reviewer_subject_digest_salt_digest: str
    browser_binding_key_digest: str
    required_attestor_id: str
    required_attestor_subject_id: str
    required_receipt_schema: str
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.required_decision_schema,
            self.required_decision_state,
            self.required_request_schema,
            self.required_request_state,
            self.required_readiness_schema,
            self.required_readiness_state,
            self.required_promotion_schema,
            self.required_promotion_state,
            self.required_attestor_id,
            self.required_attestor_subject_id,
            self.required_receipt_schema,
            self.signed_by,
            *self.allowed_dispositions,
            *self.accepted_basis_codes,
            *self.rejected_basis_codes,
            *self.forbidden_approver_role_ids,
        )
        if (
            self.version != 1
            or set(self.allowed_dispositions) != FINAL_DISPOSITIONS
            or not self.accepted_basis_codes
            or not self.rejected_basis_codes
            or set(self.accepted_basis_codes) & set(self.rejected_basis_codes)
            or len(set(self.accepted_basis_codes)) != len(self.accepted_basis_codes)
            or len(set(self.rejected_basis_codes)) != len(self.rejected_basis_codes)
            or not self.forbidden_approver_role_ids
            or len(set(self.forbidden_approver_role_ids)) != len(self.forbidden_approver_role_ids)
            or not 1 <= self.maximum_basis_codes <= 8
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 1 <= self.maximum_attestation_delay_seconds <= 300
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(
                self.source_consumer_subject_digest_salt_digest,
                self.approver_subject_digest_salt_digest,
                self.reviewer_subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Final recommendation disposition policy is invalid")


@dataclass(frozen=True, slots=True)
class FinalRecommendationDispositionInstruction:
    disposition_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    review_request_digest: str
    recommendation_id: str
    recommendation_digest: str
    promotion_id: str
    readiness_assessment_id: str
    assignment_set_id: str
    decision_ids: tuple[str, str]
    decision_digests: tuple[str, str]
    decision_aggregate_digest: str
    approver_subject_digest: str
    browser_session_binding_digest: str
    disposition_code: str
    basis_codes: tuple[str, ...]
    basis_digest: str
    policy_id: str
    policy_digest: str
    purpose_digest: str
    requested_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.disposition_id,
            self.organization_id,
            self.environment_id,
            self.review_request_id,
            self.recommendation_id,
            self.promotion_id,
            self.readiness_assessment_id,
            self.assignment_set_id,
            *self.decision_ids,
            self.disposition_code,
            *self.basis_codes,
            self.policy_id,
        )
        if (
            self.disposition_code not in FINAL_DISPOSITIONS
            or len(set(self.decision_ids)) != 2
            or len(set(self.decision_digests)) != 2
            or not self.basis_codes
            or len(set(self.basis_codes)) != len(self.basis_codes)
            or self.requested_at.tzinfo is None
            or not _digests(
                self.review_request_digest,
                self.recommendation_digest,
                *self.decision_digests,
                self.decision_aggregate_digest,
                self.approver_subject_digest,
                self.browser_session_binding_digest,
                self.basis_digest,
                self.policy_digest,
                self.purpose_digest,
            )
        ):
            raise ValueError("Final recommendation disposition instruction is invalid")


@dataclass(frozen=True, slots=True)
class FinalRecommendationDispositionReceipt:
    disposition_id: str
    schema_version: str
    version: int
    attestor_id: str
    attested_by: str
    disposition_code: str
    instruction_digest: str
    attested_at: datetime
    source_verified: bool
    no_model_used: bool
    no_network_used: bool
    no_operational_authority: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.disposition_id,
            self.schema_version,
            self.attestor_id,
            self.attested_by,
            self.disposition_code,
        )
        if (
            self.version != 1
            or self.disposition_code not in FINAL_DISPOSITIONS
            or self.attested_at.tzinfo is None
            or not all(
                (
                    self.source_verified,
                    self.no_model_used,
                    self.no_network_used,
                    self.no_operational_authority,
                    self.signature_verified,
                )
            )
            or not _digests(self.instruction_digest, self.canonical_digest)
        ):
            raise ValueError("Final recommendation disposition receipt is invalid")


@dataclass(frozen=True, slots=True)
class FinalRecommendationDispositionClaim:
    claim_id: str
    schema_version: str
    version: int
    review_request_id: str
    disposition_id: str
    organization_id: str
    environment_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    claimed_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.review_request_id,
            self.disposition_id,
            self.organization_id,
            self.environment_id,
        )
        if (
            self.version != 1
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Final recommendation disposition claim is invalid")


@dataclass(frozen=True, slots=True)
class FinalRecommendationDispositionRecord:
    disposition_id: str
    schema_version: str
    version: int
    claim_id: str
    review_request_id: str
    review_request_digest: str
    recommendation_id: str
    recommendation_digest: str
    promotion_id: str
    readiness_assessment_id: str
    assignment_set_id: str
    decision_ids: tuple[str, str]
    decision_digests: tuple[str, str]
    decision_aggregate_digest: str
    organization_id: str
    environment_id: str
    classification: str
    disposition_code: str
    basis_codes: tuple[str, ...]
    basis_digest: str
    approved_by_subject_digest: str
    browser_session_binding_digest: str
    disposition_policy_id: str
    disposition_policy_digest: str
    disposition_policy_version: str
    attestor_id: str
    attestation_digest: str
    resolved_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    technical_review_completed: bool = True
    service_impact_review_completed: bool = True
    technical_review_passed: bool = True
    service_impact_review_passed: bool = True
    correction_required: bool = False
    correction_created: bool = False
    final_disposition_recorded: bool = True
    recommendation_approved: bool = False
    workflow_handoff_eligible: bool = False
    workflow_created: bool = False
    itsm_record_created: bool = False
    change_approved: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.disposition_id,
            self.schema_version,
            self.claim_id,
            self.review_request_id,
            self.recommendation_id,
            self.promotion_id,
            self.readiness_assessment_id,
            self.assignment_set_id,
            *self.decision_ids,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.disposition_code,
            *self.basis_codes,
            self.disposition_policy_id,
            self.disposition_policy_version,
            self.attestor_id,
            self.state,
        )
        accepted = self.disposition_code == FINAL_ACCEPTED
        if (
            self.version != 1
            or self.disposition_code not in FINAL_DISPOSITIONS
            or self.state != (FINAL_ACCEPTED_STATE if accepted else FINAL_REJECTED_STATE)
            or not all(
                (
                    self.technical_review_completed,
                    self.service_impact_review_completed,
                    self.technical_review_passed,
                    self.service_impact_review_passed,
                    self.final_disposition_recorded,
                )
            )
            or self.correction_required
            or self.correction_created
            or self.recommendation_approved is not accepted
            or self.workflow_handoff_eligible is not accepted
            or any(
                (
                    self.workflow_created,
                    self.itsm_record_created,
                    self.change_approved,
                    self.execution_authorized,
                    self.deployment_authorized,
                    self.infrastructure_mutated,
                )
            )
            or len(set(self.decision_ids)) != 2
            or len(set(self.decision_digests)) != 2
            or not self.basis_codes
            or len(set(self.basis_codes)) != len(self.basis_codes)
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.resolved_at.tzinfo is None
            or not _digests(
                self.review_request_digest,
                self.recommendation_digest,
                *self.decision_digests,
                self.decision_aggregate_digest,
                self.basis_digest,
                self.approved_by_subject_digest,
                self.browser_session_binding_digest,
                self.disposition_policy_digest,
                self.attestation_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Final recommendation disposition record is invalid")
