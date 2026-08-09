from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.review_request import (
    RecommendationReviewRequestResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class RecommendationReviewRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.recommendation-review-request-input.v1", pattern=STABLE_ID
    )
    recommendation_digest: str = Field(pattern=DIGEST)
    readiness_assessment_id: str = Field(pattern=STABLE_ID)
    readiness_assessment_digest: str = Field(pattern=DIGEST)
    review_request_policy_id: str = Field(pattern=STABLE_ID)
    review_request_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_request_is_not_assignment_or_review: bool
    acknowledged_routing_is_policy_owned: bool
    acknowledged_no_approval_or_operational_authority: bool


class RecommendationReviewRequestRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_request_id: str
    recommendation_id: str
    schema_version: str
    version: int
    readiness_assessment_id: str
    promotion_id: str
    presentation_id: str
    organization_id: str
    environment_id: str
    classification: str
    review_request_policy_id: str
    review_request_policy_version: str
    orchestrator_id: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_codes: tuple[str, ...]
    queue_ids: tuple[str, ...]
    track_statuses: tuple[tuple[str, str], ...]
    routing_profile: str
    sla_class: str
    manifest_digest: str
    state: str
    requested_at: datetime
    expires_at: datetime
    purpose: str
    canonical_digest: str
    review_requested: bool
    reviewer_assigned: bool
    content_inspection_opened: bool
    human_review_completed: bool
    recommendation_approved: bool
    workflow_created: bool
    itsm_record_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool


class RecommendationReviewRequestManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_request_id: str
    recommendation_id: str
    readiness_assessment_id: str
    promotion_id: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_codes: tuple[str, ...]
    queue_ids: tuple[str, ...]
    track_statuses: tuple[tuple[str, str], ...]
    routing_profile: str
    sla_class: str
    state: str
    requested_at: datetime
    expires_at: datetime
    review_requested: bool


class RecommendationReviewRequestResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: RecommendationReviewRequestRecordData
    manifest: RecommendationReviewRequestManifestData

    @classmethod
    def from_domain(
        cls, result: RecommendationReviewRequestResult
    ) -> RecommendationReviewRequestResultData:
        return cls(
            request=RecommendationReviewRequestRecordData.model_validate(
                result.record, from_attributes=True
            ),
            manifest=RecommendationReviewRequestManifestData.model_validate(
                result.manifest, from_attributes=True
            ),
        )


class RecommendationReviewRequestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RecommendationReviewRequestResultData
    meta: ResponseMeta
