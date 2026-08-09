from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.protected_recommendation_presentation_schemas import (
    PresentedRecommendationOptionData,
)
from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.promotion import RecommendationPromotionResult

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class RecommendationPromotionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.recommendation-promotion-input.v1", pattern=STABLE_ID
    )
    presentation_digest: str = Field(pattern=DIGEST)
    promotion_policy_id: str = Field(pattern=STABLE_ID)
    promotion_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_draft_only: bool
    acknowledged_no_review_or_approval: bool
    acknowledged_no_operational_authority: bool


class PromotedRecommendationArtifactData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    promotion_id: str
    recommendation_id: str
    schema_version: str
    version: int
    presentation_id: str
    adjudication_id: str
    organization_id: str
    environment_id: str
    classification: str
    promotion_policy_id: str
    promotion_policy_version: str
    promoter_id: str
    outcome: str
    headline: str
    safety_notice: str
    options: tuple[PresentedRecommendationOptionData, ...]
    evidence_needs: tuple[str, ...]
    state: str
    promoted_at: datetime
    expires_at: datetime
    purpose: str
    byte_count: int
    canonical_digest: str
    recommendation_promoted: bool
    recommendation_ready_for_review: bool
    human_review_completed: bool
    recommendation_approved: bool
    workflow_created: bool
    itsm_record_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool


class RecommendationPromotionManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    promotion_id: str
    recommendation_id: str
    presentation_id: str
    adjudication_id: str
    outcome: str
    option_count: int
    preferred_count: int
    state: str
    promoted_at: datetime
    expires_at: datetime
    safety_notice: str


class RecommendationPromotionResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation: PromotedRecommendationArtifactData
    manifest: RecommendationPromotionManifestData

    @classmethod
    def from_domain(
        cls, result: RecommendationPromotionResult
    ) -> RecommendationPromotionResultData:
        return cls(
            recommendation=PromotedRecommendationArtifactData.model_validate(
                result.artifact, from_attributes=True
            ),
            manifest=RecommendationPromotionManifestData.model_validate(
                result.manifest, from_attributes=True
            ),
        )


class RecommendationPromotionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RecommendationPromotionResultData
    meta: ResponseMeta
