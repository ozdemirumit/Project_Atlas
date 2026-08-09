from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class RecommendationReviewerAssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.recommendation-reviewer-assignment-input.v1", pattern=STABLE_ID
    )
    review_request_id: str = Field(pattern=STABLE_ID)
    review_request_digest: str = Field(pattern=DIGEST)
    assignment_policy_id: str = Field(pattern=STABLE_ID)
    assignment_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_caller_cannot_select_reviewers: bool
    acknowledged_distinct_reviewers_required: bool
    acknowledged_no_inspection_decision_or_operational_authority: bool


class RecommendationReviewerAssignmentRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignment_set_id: str
    review_request_id: str
    recommendation_id: str
    schema_version: str
    version: int
    readiness_assessment_id: str
    promotion_id: str
    organization_id: str
    environment_id: str
    classification: str
    assignment_policy_id: str
    assignment_policy_version: str
    assignment_adapter_id: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_assignments: tuple[tuple[str, str, str, str, str], ...]
    manifest_digest: str
    state: str
    assigned_at: datetime
    expires_at: datetime
    purpose: str
    canonical_digest: str
    review_requested: bool
    reviewer_assigned: bool
    immutable_assignments_confirmed: bool
    encrypted_identity_references: bool
    transient_identity_buffers_erased: bool
    directory_channel_closed: bool
    content_inspection_opened: bool
    human_review_completed: bool
    recommendation_approved: bool
    workflow_created: bool
    itsm_record_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool


class RecommendationReviewerAssignmentManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignment_set_id: str
    review_request_id: str
    recommendation_id: str
    track_assignments: tuple[tuple[str, str, str, str, str], ...]
    state: str
    assigned_at: datetime
    expires_at: datetime
    reviewer_assigned: bool


class RecommendationReviewerAssignmentResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignment: RecommendationReviewerAssignmentRecordData
    manifest: RecommendationReviewerAssignmentManifestData

    @classmethod
    def from_domain(
        cls, result: RecommendationReviewerAssignmentResult
    ) -> RecommendationReviewerAssignmentResultData:
        return cls(
            assignment=RecommendationReviewerAssignmentRecordData.model_validate(
                result.record, from_attributes=True
            ),
            manifest=RecommendationReviewerAssignmentManifestData.model_validate(
                result.manifest, from_attributes=True
            ),
        )


class RecommendationReviewerAssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RecommendationReviewerAssignmentResultData
    meta: ResponseMeta
