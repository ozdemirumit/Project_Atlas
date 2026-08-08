from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateManifest,
    ProtectedRecommendationCandidateRecord,
    ProtectedRecommendationCandidateResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ProtectedRecommendationCandidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.protected-recommendation-candidate-input.v1", pattern=STABLE_ID
    )
    presentation_digest: str = Field(pattern=DIGEST)
    generation_policy_id: str = Field(pattern=STABLE_ID)
    generation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_candidates_are_incomplete: bool
    acknowledged_impact_and_recovery_are_unverified: bool
    acknowledged_no_recommendation_or_operational_authority: bool


class ProtectedRecommendationCandidateData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_set_id: str
    schema_version: str
    version: int
    presentation_id: str
    presentation_digest: str
    answer_digest: str
    adjudication_id: str
    adjudication_digest: str
    invocation_id: str
    invocation_digest: str
    context_id: str
    context_digest: str
    draft_digest: str
    report_digest: str
    organization_id: str
    environment_id: str
    classification: str
    generation_policy_id: str
    generation_policy_digest: str
    generation_policy_version: str
    generator_id: str
    generation_receipt_digest: str
    candidate_content_digest: str
    source_binding_digest: str
    citation_set_digest: str
    unknown_set_digest: str
    safety_digest: str
    cleanup_digest: str
    candidate_categories: tuple[str, ...]
    maximum_capability_class: str
    candidate_count: int
    step_count: int
    citation_count: int
    unknown_count: int
    byte_count: int
    generated_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    recommendation_candidates_generated: bool
    service_impact_analyzed: bool
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
        cls, record: ProtectedRecommendationCandidateRecord
    ) -> ProtectedRecommendationCandidateData:
        return cls.model_validate(record, from_attributes=True)


class ProtectedRecommendationCandidateManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_set_id: str
    presentation_id: str
    adjudication_id: str
    invocation_id: str
    context_id: str
    candidate_categories: tuple[str, ...]
    maximum_capability_class: str
    candidate_count: int
    step_count: int
    citation_count: int
    unknown_count: int
    byte_count: int
    candidate_content_digest: str
    source_binding_digest: str
    citation_set_digest: str
    unknown_set_digest: str
    safety_digest: str
    cleanup_digest: str
    generated_at: datetime
    expires_at: datetime

    @classmethod
    def from_domain(
        cls, manifest: ProtectedRecommendationCandidateManifest
    ) -> ProtectedRecommendationCandidateManifestData:
        return cls.model_validate(manifest, from_attributes=True)


class ProtectedRecommendationCandidateResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_set: ProtectedRecommendationCandidateData
    manifest: ProtectedRecommendationCandidateManifestData

    @classmethod
    def from_domain(
        cls, result: ProtectedRecommendationCandidateResult
    ) -> ProtectedRecommendationCandidateResultData:
        return cls(
            candidate_set=ProtectedRecommendationCandidateData.from_domain(result.record),
            manifest=ProtectedRecommendationCandidateManifestData.from_domain(result.manifest),
        )


class ProtectedRecommendationCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ProtectedRecommendationCandidateResultData
    meta: ResponseMeta
