from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

RECOMMENDATION_TRACK_REVIEW_DECIDED = "recommendation_track_review_decided"
TRACKS = frozenset(("review-track.technical", "review-track.service-impact"))
DISPOSITIONS = frozenset(("review-disposition.passed", "review-disposition.changes-required"))
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "recommendation review decision identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class RecommendationTrackReviewDecisionPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_source_schema: str
    required_source_state: str
    required_attestor_id: str
    required_attestor_subject_id: str
    required_receipt_schema: str
    subject_digest_salt_digest: str
    maximum_authentication_age_minutes: int
    allowed_dispositions: tuple[str, ...]
    technical_basis_codes: tuple[str, ...]
    service_impact_basis_codes: tuple[str, ...]
    maximum_basis_codes: int
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
            self.required_source_schema,
            self.required_source_state,
            self.required_attestor_id,
            self.required_attestor_subject_id,
            self.required_receipt_schema,
            self.signed_by,
            *self.allowed_dispositions,
            *self.technical_basis_codes,
            *self.service_impact_basis_codes,
        )
        if (
            self.version != 1
            or frozenset(self.allowed_dispositions) != DISPOSITIONS
            or len(set(self.technical_basis_codes)) != len(self.technical_basis_codes)
            or len(set(self.service_impact_basis_codes)) != len(self.service_impact_basis_codes)
            or not 1 <= self.maximum_basis_codes <= 8
            or not self.technical_basis_codes
            or not self.service_impact_basis_codes
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
            or not _digests(self.subject_digest_salt_digest, self.canonical_digest)
        ):
            raise ValueError("Recommendation review decision policy is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationTrackReviewDecisionInstruction:
    decision_id: str
    organization_id: str
    environment_id: str
    source_finding_presentation_id: str
    source_finding_presentation_digest: str
    source_finding_packet_id: str
    source_finding_digest: str
    source_lease_id: str
    source_assignment_set_id: str
    review_request_id: str
    source_review_request_digest: str
    recommendation_id: str
    readiness_assessment_id: str
    promotion_id: str
    recommendation_artifact_digest: str
    presented_content_digest: str
    track_code: str
    disposition_code: str
    basis_codes: tuple[str, ...]
    decision_policy_digest: str
    decided_by_subject_digest: str
    browser_session_binding_digest: str
    purpose_digest: str
    decided_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.decision_id,
            self.organization_id,
            self.environment_id,
            self.source_finding_presentation_id,
            self.source_finding_packet_id,
            self.source_lease_id,
            self.source_assignment_set_id,
            self.review_request_id,
            self.recommendation_id,
            self.readiness_assessment_id,
            self.promotion_id,
            self.track_code,
            self.disposition_code,
            *self.basis_codes,
        )
        if (
            self.track_code not in TRACKS
            or self.disposition_code not in DISPOSITIONS
            or not self.basis_codes
            or len(set(self.basis_codes)) != len(self.basis_codes)
            or self.decided_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.decided_at < self.expires_at
            or not _digests(
                self.source_finding_presentation_digest,
                self.source_finding_digest,
                self.source_review_request_digest,
                self.recommendation_artifact_digest,
                self.presented_content_digest,
                self.decision_policy_digest,
                self.decided_by_subject_digest,
                self.browser_session_binding_digest,
                self.purpose_digest,
            )
        ):
            raise ValueError("Recommendation review decision instruction is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationTrackReviewDecisionReceipt:
    decision_id: str
    schema_version: str
    version: int
    attestor_id: str
    attested_by: str
    source_finding_presentation_id: str
    source_finding_presentation_digest: str
    track_code: str
    disposition_code: str
    basis_digest: str
    instruction_digest: str
    attested_at: datetime
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.decision_id,
            self.schema_version,
            self.attestor_id,
            self.attested_by,
            self.source_finding_presentation_id,
            self.track_code,
            self.disposition_code,
        )
        if (
            self.version != 1
            or self.track_code not in TRACKS
            or self.disposition_code not in DISPOSITIONS
            or self.attested_at.tzinfo is None
            or not self.signature_verified
            or not _digests(
                self.source_finding_presentation_digest,
                self.basis_digest,
                self.instruction_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation review decision receipt is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationTrackReviewDecisionClaim:
    claim_id: str
    schema_version: str
    version: int
    source_finding_presentation_id: str
    source_finding_presentation_digest: str
    decision_id: str
    organization_id: str
    environment_id: str
    track_code: str
    disposition_code: str
    basis_digest: str
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
            self.source_finding_presentation_id,
            self.decision_id,
            self.organization_id,
            self.environment_id,
            self.track_code,
            self.disposition_code,
        )
        if (
            self.version != 1
            or self.track_code not in TRACKS
            or self.disposition_code not in DISPOSITIONS
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_finding_presentation_digest,
                self.basis_digest,
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.purpose_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation review decision claim is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationTrackReviewDecisionRecord:
    decision_id: str
    schema_version: str
    version: int
    claim_id: str
    source_finding_presentation_id: str
    source_finding_presentation_digest: str
    source_finding_packet_id: str
    source_finding_digest: str
    source_lease_id: str
    source_lease_digest: str
    source_content_presentation_id: str
    source_assignment_set_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    source_review_request_digest: str
    recommendation_id: str
    readiness_assessment_id: str
    promotion_id: str
    recommendation_artifact_digest: str
    presented_content_digest: str
    classification: str
    source_outcome: str
    option_count: int
    preferred_count: int
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
    track_code: str
    disposition_code: str
    basis_codes: tuple[str, ...]
    basis_digest: str
    decided_by_subject_digest: str
    browser_session_binding_digest: str
    decision_policy_id: str
    decision_policy_digest: str
    decision_policy_version: str
    attestor_id: str
    attestation_digest: str
    decided_at: datetime
    expires_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    review_requested: bool = True
    reviewer_assigned: bool = True
    content_inspection_opened: bool = True
    content_disclosed: bool = True
    human_findings_recorded: bool = True
    human_findings_presented: bool = True
    exact_assignee_verified: bool = True
    browser_session_bound: bool = True
    technical_review_completed: bool = False
    service_impact_review_completed: bool = False
    technical_review_passed: bool = False
    service_impact_review_passed: bool = False
    correction_required: bool = False
    correction_created: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    itsm_record_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.decision_id,
            self.schema_version,
            self.claim_id,
            self.source_finding_presentation_id,
            self.source_finding_packet_id,
            self.source_lease_id,
            self.source_content_presentation_id,
            self.source_assignment_set_id,
            self.organization_id,
            self.environment_id,
            self.review_request_id,
            self.recommendation_id,
            self.readiness_assessment_id,
            self.promotion_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.track_code,
            self.disposition_code,
            self.decision_policy_id,
            self.decision_policy_version,
            self.attestor_id,
            self.state,
            *self.basis_codes,
        )
        technical_expected = self.track_code == "review-track.technical"
        passed = self.disposition_code == "review-disposition.passed"
        later_authority = (
            self.correction_created,
            self.recommendation_approved,
            self.workflow_created,
            self.itsm_record_created,
            self.execution_authorized,
            self.deployment_authorized,
            self.infrastructure_mutated,
        )
        if (
            self.version != 1
            or self.state != RECOMMENDATION_TRACK_REVIEW_DECIDED
            or self.track_code not in TRACKS
            or self.disposition_code not in DISPOSITIONS
            or self.source_outcome not in {"preferred", "tie", "no_support"}
            or not 1 <= self.option_count <= 5
            or not 0 <= self.preferred_count <= self.option_count
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not self.basis_codes
            or len(set(self.basis_codes)) != len(self.basis_codes)
            or self.decided_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.decided_at < self.expires_at
            or self.technical_review_completed is not technical_expected
            or self.service_impact_review_completed is technical_expected
            or self.technical_review_passed is not (technical_expected and passed)
            or self.service_impact_review_passed is not ((not technical_expected) and passed)
            or self.correction_required is not (not passed)
            or not all(
                (
                    self.review_requested,
                    self.reviewer_assigned,
                    self.content_inspection_opened,
                    self.content_disclosed,
                    self.human_findings_recorded,
                    self.human_findings_presented,
                    self.exact_assignee_verified,
                    self.browser_session_bound,
                )
            )
            or any(later_authority)
            or not _digests(
                self.source_finding_presentation_digest,
                self.source_finding_digest,
                self.source_lease_digest,
                self.source_review_request_digest,
                self.recommendation_artifact_digest,
                self.presented_content_digest,
                self.basis_digest,
                self.decided_by_subject_digest,
                self.browser_session_binding_digest,
                self.decision_policy_digest,
                self.attestation_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation review decision record is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationTrackDecisionBinding:
    track_code: str
    decision_id: str
    canonical_digest: str
    disposition_code: str

    def __post_init__(self) -> None:
        _ids(self.track_code, self.decision_id, self.disposition_code)
        if (
            self.track_code not in TRACKS
            or self.disposition_code not in DISPOSITIONS
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Recommendation track decision binding is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationTrackReviewDecisionGrant:
    record: RecommendationTrackReviewDecisionRecord
    all_tracks_decided: bool
    all_tracks_passed: bool
    any_correction_required: bool
    track_decisions: tuple[RecommendationTrackDecisionBinding, ...]

    def __post_init__(self) -> None:
        tracks = {item.track_code for item in self.track_decisions}
        if (
            len(tracks) != len(self.track_decisions)
            or self.record.track_code not in tracks
            or self.all_tracks_decided is not (tracks == TRACKS)
            or self.any_correction_required
            is not any(
                item.disposition_code == "review-disposition.changes-required"
                for item in self.track_decisions
            )
            or (
                self.all_tracks_passed
                and (not self.all_tracks_decided or self.any_correction_required)
            )
        ):
            raise ValueError("Recommendation review decision aggregate is invalid")
