from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

RECOMMENDATION_CORRECTION_RESUBMITTED = "recommendation_correction_resubmitted"
TRACKS = frozenset(("review-track.technical", "review-track.service-impact"))
CHANGES_REQUIRED = "review-disposition.changes-required"
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "recommendation correction identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class RecommendationCorrectionPolicySnapshot:
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
    required_promotion_schema: str
    required_promotion_state: str
    required_adapter_id: str
    required_adapter_attestor_id: str
    required_receipt_schema: str
    technical_track_code: str
    service_impact_track_code: str
    source_consumer_subject_digest_salt_digest: str
    subject_digest_salt_digest: str
    reviewer_subject_digest_salt_digest: str
    browser_binding_key_digest: str
    maximum_authentication_age_minutes: int
    retention_minutes: int
    required_assurance_level: AssuranceLevel
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
            self.required_promotion_schema,
            self.required_promotion_state,
            self.required_adapter_id,
            self.required_adapter_attestor_id,
            self.required_receipt_schema,
            self.technical_track_code,
            self.service_impact_track_code,
            self.signed_by,
        )
        if (
            self.version != 1
            or {self.technical_track_code, self.service_impact_track_code} != TRACKS
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 1 <= self.retention_minutes <= 1440
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
                self.subject_digest_salt_digest,
                self.reviewer_subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation correction policy is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationCorrectionInstruction:
    correction_id: str
    source_review_request_id: str
    source_review_request_digest: str
    source_recommendation_id: str
    source_recommendation_digest: str
    source_promotion_id: str
    source_readiness_assessment_id: str
    source_assignment_set_id: str
    source_decision_ids: tuple[str, str]
    source_decision_digests: tuple[str, str]
    decision_aggregate_digest: str
    correction_submission_id: str
    correction_submission_digest: str
    organization_id: str
    environment_id: str
    new_recommendation_id: str
    new_promotion_id: str
    corrected_by_subject_digest: str
    browser_session_binding_digest: str
    correction_policy_digest: str
    requested_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.correction_id,
            self.source_review_request_id,
            self.source_recommendation_id,
            self.source_promotion_id,
            self.source_readiness_assessment_id,
            self.source_assignment_set_id,
            *self.source_decision_ids,
            self.correction_submission_id,
            self.organization_id,
            self.environment_id,
            self.new_recommendation_id,
            self.new_promotion_id,
        )
        if (
            len(set(self.source_decision_ids)) != 2
            or len(set(self.source_decision_digests)) != 2
            or self.requested_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.requested_at
            or not _digests(
                self.source_review_request_digest,
                self.source_recommendation_digest,
                *self.source_decision_digests,
                self.decision_aggregate_digest,
                self.correction_submission_digest,
                self.corrected_by_subject_digest,
                self.browser_session_binding_digest,
                self.correction_policy_digest,
            )
        ):
            raise ValueError("Recommendation correction instruction is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationCorrectionReceipt:
    correction_id: str
    schema_version: str
    version: int
    adapter_id: str
    attested_by: str
    source_review_request_id: str
    source_review_request_digest: str
    decision_aggregate_digest: str
    correction_submission_id: str
    correction_submission_digest: str
    new_recommendation_id: str
    new_promotion_id: str
    new_artifact_digest: str
    source_binding_digest: str
    corrected_at: datetime
    expires_at: datetime
    source_verified: bool
    corrected_version_immutable: bool
    safe_content_verified: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    no_model_used: bool
    no_network_used: bool
    no_operational_authority: bool
    signature_verified: bool
    instruction_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.correction_id,
            self.schema_version,
            self.adapter_id,
            self.attested_by,
            self.source_review_request_id,
            self.correction_submission_id,
            self.new_recommendation_id,
            self.new_promotion_id,
        )
        if (
            self.version != 1
            or self.corrected_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.corrected_at
            or not all(
                (
                    self.source_verified,
                    self.corrected_version_immutable,
                    self.safe_content_verified,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                    self.no_model_used,
                    self.no_network_used,
                    self.no_operational_authority,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.source_review_request_digest,
                self.decision_aggregate_digest,
                self.correction_submission_digest,
                self.new_artifact_digest,
                self.source_binding_digest,
                self.instruction_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation correction receipt is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationCorrectionClaim:
    claim_id: str
    schema_version: str
    version: int
    source_review_request_id: str
    source_review_request_digest: str
    correction_id: str
    organization_id: str
    environment_id: str
    decision_aggregate_digest: str
    correction_submission_digest: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    purpose_digest: str
    claimed_at: datetime
    request_binding_digest: str
    idempotency_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.source_review_request_id,
            self.correction_id,
            self.organization_id,
            self.environment_id,
        )
        if (
            self.version != 1
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_review_request_digest,
                self.decision_aggregate_digest,
                self.correction_submission_digest,
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.purpose_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation correction claim is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationCorrectionRecord:
    correction_id: str
    schema_version: str
    version: int
    claim_id: str
    source_review_request_id: str
    source_review_request_digest: str
    source_recommendation_id: str
    source_recommendation_digest: str
    source_promotion_id: str
    source_readiness_assessment_id: str
    source_assignment_set_id: str
    source_decision_ids: tuple[str, str]
    source_decision_digests: tuple[str, str]
    decision_aggregate_digest: str
    organization_id: str
    environment_id: str
    classification: str
    corrected_by_subject_digest: str
    browser_session_binding_digest: str
    correction_submission_id: str
    correction_submission_digest: str
    correction_policy_id: str
    correction_policy_digest: str
    correction_policy_version: str
    adapter_id: str
    attestation_digest: str
    new_recommendation_id: str
    new_promotion_id: str
    new_artifact_digest: str
    source_binding_digest: str
    created_at: datetime
    expires_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    recommendation_promoted: bool = True
    correction_created: bool = True
    readiness_assessed: bool = False
    review_requested: bool = False
    reviewer_assigned: bool = False
    protected_inspection_opened: bool = False
    human_findings_recorded: bool = False
    technical_review_completed: bool = False
    service_impact_review_completed: bool = False
    final_disposition_recorded: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    itsm_record_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.correction_id,
            self.schema_version,
            self.claim_id,
            self.source_review_request_id,
            self.source_recommendation_id,
            self.source_promotion_id,
            self.source_readiness_assessment_id,
            self.source_assignment_set_id,
            *self.source_decision_ids,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.correction_submission_id,
            self.correction_policy_id,
            self.correction_policy_version,
            self.adapter_id,
            self.new_recommendation_id,
            self.new_promotion_id,
            self.state,
        )
        if (
            self.version != 1
            or self.state != RECOMMENDATION_CORRECTION_RESUBMITTED
            or len(set(self.source_decision_ids)) != 2
            or len(set(self.source_decision_digests)) != 2
            or self.created_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.created_at
            or not self.recommendation_promoted
            or not self.correction_created
            or any(
                (
                    self.readiness_assessed,
                    self.review_requested,
                    self.reviewer_assigned,
                    self.protected_inspection_opened,
                    self.human_findings_recorded,
                    self.technical_review_completed,
                    self.service_impact_review_completed,
                    self.final_disposition_recorded,
                    self.recommendation_approved,
                    self.workflow_created,
                    self.itsm_record_created,
                    self.execution_authorized,
                    self.deployment_authorized,
                    self.infrastructure_mutated,
                )
            )
            or not _digests(
                self.source_review_request_digest,
                self.source_recommendation_digest,
                *self.source_decision_digests,
                self.decision_aggregate_digest,
                self.corrected_by_subject_digest,
                self.browser_session_binding_digest,
                self.correction_submission_digest,
                self.correction_policy_digest,
                self.attestation_digest,
                self.new_artifact_digest,
                self.source_binding_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation correction record is invalid")
