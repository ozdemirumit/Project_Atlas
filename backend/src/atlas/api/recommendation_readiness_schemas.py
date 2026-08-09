from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessResult

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class RecommendationReadinessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.recommendation-readiness-input.v1", pattern=STABLE_ID
    )
    recommendation_digest: str = Field(pattern=DIGEST)
    readiness_policy_id: str = Field(pattern=STABLE_ID)
    readiness_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_readiness_is_not_review: bool
    acknowledged_blocked_requires_new_version: bool
    acknowledged_no_operational_authority: bool


class RecommendationReadinessAssessmentData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_id: str
    recommendation_id: str
    schema_version: str
    version: int
    promotion_id: str
    presentation_id: str
    organization_id: str
    environment_id: str
    classification: str
    readiness_policy_id: str
    readiness_policy_version: str
    evaluator_id: str
    source_outcome: str
    option_count: int
    preferred_count: int
    evaluation_outcome: str
    reason_codes: tuple[str, ...]
    check_count: int
    passed_check_count: int
    state: str
    assessed_at: datetime
    expires_at: datetime
    purpose: str
    canonical_digest: str
    recommendation_ready_for_review: bool
    human_review_completed: bool
    recommendation_approved: bool
    workflow_created: bool
    itsm_record_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool


class RecommendationReadinessManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_id: str
    recommendation_id: str
    promotion_id: str
    source_outcome: str
    option_count: int
    preferred_count: int
    evaluation_outcome: str
    reason_codes: tuple[str, ...]
    check_count: int
    passed_check_count: int
    state: str
    assessed_at: datetime
    expires_at: datetime
    recommendation_ready_for_review: bool


class RecommendationReadinessResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment: RecommendationReadinessAssessmentData
    manifest: RecommendationReadinessManifestData

    @classmethod
    def from_domain(
        cls, result: RecommendationReadinessResult
    ) -> RecommendationReadinessResultData:
        return cls(
            assessment=RecommendationReadinessAssessmentData.model_validate(
                result.assessment, from_attributes=True
            ),
            manifest=RecommendationReadinessManifestData.model_validate(
                result.manifest, from_attributes=True
            ),
        )


class RecommendationReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RecommendationReadinessResultData
    meta: ResponseMeta
