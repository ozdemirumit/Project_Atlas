from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.review_decision import (
    RecommendationTrackReviewDecisionGrant,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class RecommendationTrackReviewDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.recommendation-track-review-decision-input.v1",
        pattern=STABLE_ID,
    )
    source_finding_presentation_digest: str = Field(pattern=DIGEST)
    decision_policy_id: str = Field(pattern=STABLE_ID)
    decision_policy_digest: str = Field(pattern=DIGEST)
    disposition_code: str = Field(pattern=STABLE_ID)
    basis_codes: tuple[str, ...] = Field(min_length=1, max_length=4)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_exact_findings_reviewed: bool
    acknowledged_human_track_decision: bool
    acknowledged_no_approval_or_operational_authority: bool


class RecommendationTrackDecisionBindingData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    track_code: str
    decision_id: str
    canonical_digest: str
    disposition_code: str


class RecommendationTrackReviewDecisionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    schema_version: str
    version: int
    source_finding_presentation_id: str
    source_finding_presentation_digest: str
    source_finding_packet_id: str
    source_lease_id: str
    source_content_presentation_id: str
    source_assignment_set_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    source_review_request_digest: str
    recommendation_id: str
    readiness_assessment_id: str
    promotion_id: str
    classification: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_code: str
    disposition_code: str
    basis_codes: tuple[str, ...]
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
    technical_review_completed: bool
    service_impact_review_completed: bool
    technical_review_passed: bool
    service_impact_review_passed: bool
    correction_required: bool
    correction_created: bool
    all_tracks_decided: bool
    all_tracks_passed: bool
    any_correction_required: bool
    track_decisions: tuple[RecommendationTrackDecisionBindingData, ...]
    recommendation_approved: bool
    workflow_created: bool
    itsm_record_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool

    @classmethod
    def from_grant(
        cls, grant: RecommendationTrackReviewDecisionGrant
    ) -> RecommendationTrackReviewDecisionData:
        values = {
            field: getattr(grant.record, field)
            for field in cls.model_fields
            if field
            not in {
                "all_tracks_decided",
                "all_tracks_passed",
                "any_correction_required",
                "track_decisions",
            }
        }
        values.update(
            all_tracks_decided=grant.all_tracks_decided,
            all_tracks_passed=grant.all_tracks_passed,
            any_correction_required=grant.any_correction_required,
            track_decisions=grant.track_decisions,
        )
        return cls.model_validate(values)


class RecommendationTrackReviewDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: RecommendationTrackReviewDecisionData
    meta: ResponseMeta
