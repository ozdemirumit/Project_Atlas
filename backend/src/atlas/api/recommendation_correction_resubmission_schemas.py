from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.correction_resubmission import (
    RecommendationCorrectionRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"
StableId = Annotated[str, Field(pattern=STABLE_ID)]
Digest = Annotated[str, Field(pattern=DIGEST)]


class RecommendationCorrectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.recommendation-correction-input.v1", pattern=STABLE_ID
    )
    source_review_request_digest: str = Field(pattern=DIGEST)
    source_recommendation_id: str = Field(pattern=STABLE_ID)
    source_recommendation_digest: str = Field(pattern=DIGEST)
    source_decision_ids: tuple[StableId, StableId]
    source_decision_digests: tuple[Digest, Digest]
    correction_submission_id: str = Field(pattern=STABLE_ID)
    correction_submission_digest: str = Field(pattern=DIGEST)
    correction_policy_id: str = Field(pattern=STABLE_ID)
    correction_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_exact_change_requirements_addressed: bool
    acknowledged_new_immutable_recommendation_version: bool
    acknowledged_fresh_readiness_required: bool
    acknowledged_no_review_approval_or_operational_authority: bool


class RecommendationCorrectionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correction_id: str
    schema_version: str
    version: int
    source_review_request_id: str
    source_review_request_digest: str
    source_recommendation_id: str
    source_recommendation_digest: str
    source_promotion_id: str
    source_readiness_assessment_id: str
    source_assignment_set_id: str
    source_decision_ids: tuple[str, str]
    source_decision_digests: tuple[str, str]
    decision_aggregate_digest: str
    organization_id: str
    environment_id: str
    classification: str
    correction_submission_id: str
    correction_submission_digest: str
    correction_policy_id: str
    correction_policy_digest: str
    correction_policy_version: str
    adapter_id: str
    attestation_digest: str
    new_recommendation_id: str
    new_promotion_id: str
    new_artifact_digest: str
    source_binding_digest: str
    created_at: datetime
    expires_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    recommendation_promoted: bool
    correction_created: bool
    readiness_assessed: bool
    review_requested: bool
    reviewer_assigned: bool
    protected_inspection_opened: bool
    human_findings_recorded: bool
    technical_review_completed: bool
    service_impact_review_completed: bool
    final_disposition_recorded: bool
    recommendation_approved: bool
    workflow_created: bool
    itsm_record_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool

    @classmethod
    def from_domain(cls, record: RecommendationCorrectionRecord) -> RecommendationCorrectionData:
        return cls.model_validate(record, from_attributes=True)


class RecommendationCorrectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: RecommendationCorrectionData
    meta: ResponseMeta
