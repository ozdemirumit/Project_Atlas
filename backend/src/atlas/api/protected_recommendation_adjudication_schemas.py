from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.ai.domain.protected_recommendation_adjudication import (
    ProtectedRecommendationAdjudicationManifest,
    ProtectedRecommendationAdjudicationRecord,
    ProtectedRecommendationAdjudicationResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ProtectedRecommendationAdjudicationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.protected-recommendation-adjudication-input.v1",
        pattern=STABLE_ID,
    )
    completion_digest: str = Field(pattern=DIGEST)
    adjudication_policy_id: str = Field(pattern=STABLE_ID)
    adjudication_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_preference_is_not_approval: bool
    acknowledged_tie_or_no_support_is_valid: bool
    acknowledged_no_presentation_or_operational_authority: bool


class ProtectedRecommendationAdjudicationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adjudication_id: str
    schema_version: str
    version: int
    completion_id: str
    completion_digest: str
    impact_analysis_id: str
    candidate_set_id: str
    candidate_set_digest: str
    presentation_id: str
    organization_id: str
    environment_id: str
    classification: str
    adjudication_policy_id: str
    adjudication_policy_digest: str
    adjudication_policy_version: str
    adjudicator_id: str
    adjudication_receipt_digest: str
    candidate_count: int
    dimension_count: int
    eligible_count: int
    excluded_count: int
    preferred_count: int
    alternative_count: int
    tie: bool
    no_supportable_candidate: bool
    maximum_risk: str
    interruption_possible_count: int
    recovery_feasible_count: int
    gap_count: int
    unknown_count: int
    comparison_digest: str
    eligibility_digest: str
    exclusion_digest: str
    preference_digest: str
    safety_digest: str
    cleanup_digest: str
    byte_count: int
    adjudicated_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    safety_notice: str
    canonical_digest: str
    service_impact_analyzed: bool
    impact_complete: bool
    interruption_established: bool
    duration_established: bool
    risk_completed: bool
    recovery_completed: bool
    recommendation_complete: bool
    recommendation_presented: bool
    recommendation_ready_for_review: bool
    recommendation_approved: bool
    workflow_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ProtectedRecommendationAdjudicationRecord
    ) -> ProtectedRecommendationAdjudicationData:
        return cls.model_validate(record, from_attributes=True)


class ProtectedRecommendationAdjudicationManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adjudication_id: str
    completion_id: str
    candidate_set_id: str
    candidate_count: int
    dimension_count: int
    eligible_count: int
    excluded_count: int
    preferred_count: int
    alternative_count: int
    tie: bool
    no_supportable_candidate: bool
    maximum_risk: str
    interruption_possible_count: int
    recovery_feasible_count: int
    gap_count: int
    unknown_count: int
    comparison_digest: str
    eligibility_digest: str
    exclusion_digest: str
    preference_digest: str
    safety_digest: str
    adjudicated_at: datetime
    expires_at: datetime
    safety_notice: str

    @classmethod
    def from_domain(
        cls, manifest: ProtectedRecommendationAdjudicationManifest
    ) -> ProtectedRecommendationAdjudicationManifestData:
        return cls.model_validate(manifest, from_attributes=True)


class ProtectedRecommendationAdjudicationResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adjudication: ProtectedRecommendationAdjudicationData
    manifest: ProtectedRecommendationAdjudicationManifestData

    @classmethod
    def from_domain(
        cls, result: ProtectedRecommendationAdjudicationResult
    ) -> ProtectedRecommendationAdjudicationResultData:
        return cls(
            adjudication=ProtectedRecommendationAdjudicationData.from_domain(result.record),
            manifest=ProtectedRecommendationAdjudicationManifestData.from_domain(result.manifest),
        )


class ProtectedRecommendationAdjudicationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ProtectedRecommendationAdjudicationResultData
    meta: ResponseMeta
