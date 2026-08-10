from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.final_disposition import (
    FinalRecommendationDispositionRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"
StableId = Annotated[str, Field(pattern=STABLE_ID)]
Digest = Annotated[str, Field(pattern=DIGEST)]


class FinalRecommendationDispositionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.final-recommendation-disposition-input.v1", pattern=STABLE_ID
    )
    review_request_digest: str = Field(pattern=DIGEST)
    recommendation_id: str = Field(pattern=STABLE_ID)
    recommendation_digest: str = Field(pattern=DIGEST)
    decision_ids: tuple[StableId, StableId]
    decision_digests: tuple[Digest, Digest]
    disposition_code: str = Field(pattern=STABLE_ID)
    basis_codes: tuple[StableId, ...] = Field(min_length=1, max_length=8)
    disposition_policy_id: str = Field(pattern=STABLE_ID)
    disposition_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_immutable_review_generation: bool
    acknowledged_recommendation_level_decision_only: bool
    acknowledged_handoff_eligibility_only: bool
    acknowledged_no_workflow_itsm_change_or_operational_authority: bool


class FinalRecommendationDispositionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition_id: str
    schema_version: str
    version: int
    review_request_id: str
    review_request_digest: str
    recommendation_id: str
    recommendation_digest: str
    promotion_id: str
    readiness_assessment_id: str
    assignment_set_id: str
    decision_ids: tuple[str, str]
    decision_digests: tuple[str, str]
    decision_aggregate_digest: str
    organization_id: str
    environment_id: str
    classification: str
    disposition_code: str
    basis_codes: tuple[str, ...]
    basis_digest: str
    disposition_policy_id: str
    disposition_policy_digest: str
    disposition_policy_version: str
    attestor_id: str
    attestation_digest: str
    resolved_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    technical_review_completed: bool
    service_impact_review_completed: bool
    technical_review_passed: bool
    service_impact_review_passed: bool
    correction_required: bool
    correction_created: bool
    final_disposition_recorded: bool
    recommendation_approved: bool
    workflow_handoff_eligible: bool
    workflow_created: bool
    itsm_record_created: bool
    change_approved: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: FinalRecommendationDispositionRecord
    ) -> FinalRecommendationDispositionData:
        return cls.model_validate(record, from_attributes=True)


class FinalRecommendationDispositionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: FinalRecommendationDispositionData
    meta: ResponseMeta
