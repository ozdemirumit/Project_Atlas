from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.ai.domain.protected_recommendation_presentation import (
    ProtectedRecommendationPresentationResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ProtectedRecommendationPresentationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.protected-recommendation-presentation-input.v1", pattern=STABLE_ID
    )
    adjudication_digest: str = Field(pattern=DIGEST)
    presentation_policy_id: str = Field(pattern=STABLE_ID)
    presentation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_decision_support_only: bool
    acknowledged_tie_or_no_support_is_valid: bool
    acknowledged_no_operational_authority: bool


class PresentedRecommendationStepData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order: int
    phase: str
    conceptual_action: str
    capability_class: str


class PresentedRecommendationOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    category: str
    title: str
    intended_outcome: str
    rationale: str
    confidence: str
    confidence_rationale: str
    steps: tuple[PresentedRecommendationStepData, ...]
    overall_risk: str
    work_minimum_minutes: int
    work_maximum_minutes: int
    interruption_expected_mode: str
    interruption_minimum_minutes: int
    interruption_maximum_minutes: int
    recovery_feasibility: str
    recovery_minimum_minutes: int
    recovery_maximum_minutes: int
    technical_service_count: int
    business_service_count: int
    evidence_references: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    applicability_limits: tuple[str, ...]
    support_reasons: tuple[str, ...]


class ProtectedPresentedRecommendationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation_id: str
    outcome: str
    headline: str
    safety_notice: str
    options: tuple[PresentedRecommendationOptionData, ...]
    evidence_needs: tuple[str, ...]
    media_type: str
    byte_count: int
    presented_at: datetime
    expires_at: datetime
    canonical_digest: str


class ProtectedRecommendationPresentationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation_id: str
    schema_version: str
    version: int
    adjudication_id: str
    adjudication_digest: str
    completion_id: str
    candidate_set_id: str
    impact_analysis_id: str
    organization_id: str
    environment_id: str
    classification: str
    presentation_policy_id: str
    presentation_policy_digest: str
    presentation_policy_version: str
    presenter_id: str
    presentation_receipt_digest: str
    outcome: str
    option_count: int
    preferred_count: int
    evidence_reference_count: int
    unknown_count: int
    byte_count: int
    media_type: str
    presented_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    safety_notice: str
    canonical_digest: str
    recommendation_presented: bool
    recommendation_ready_for_review: bool
    recommendation_approved: bool
    workflow_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool


class ProtectedRecommendationPresentationManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation_id: str
    adjudication_id: str
    completion_id: str
    candidate_set_id: str
    impact_analysis_id: str
    outcome: str
    option_count: int
    preferred_count: int
    evidence_reference_count: int
    unknown_count: int
    byte_count: int
    media_type: str
    recommendation_digest: str
    presented_at: datetime
    expires_at: datetime
    safety_notice: str


class ProtectedRecommendationPresentationResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation: ProtectedRecommendationPresentationData
    manifest: ProtectedRecommendationPresentationManifestData
    recommendation: ProtectedPresentedRecommendationData

    @classmethod
    def from_domain(
        cls, result: ProtectedRecommendationPresentationResult
    ) -> ProtectedRecommendationPresentationResultData:
        return cls(
            presentation=ProtectedRecommendationPresentationData.model_validate(
                result.record, from_attributes=True
            ),
            manifest=ProtectedRecommendationPresentationManifestData.model_validate(
                result.manifest, from_attributes=True
            ),
            recommendation=ProtectedPresentedRecommendationData.model_validate(
                result.recommendation, from_attributes=True
            ),
        )


class ProtectedRecommendationPresentationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ProtectedRecommendationPresentationResultData
    meta: ResponseMeta
