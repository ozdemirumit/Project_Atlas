from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.human_review_finding import (
    RecommendationHumanReviewFindingRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class RecommendationHumanReviewFindingItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_code: str = Field(pattern=STABLE_ID)
    severity_code: str = Field(pattern=STABLE_ID)
    summary: str = Field(min_length=10, max_length=200)
    detail: str = Field(min_length=20, max_length=4000)


class RecommendationHumanReviewFindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.recommendation-human-review-finding-input.v1", pattern=STABLE_ID
    )
    source_presentation_digest: str = Field(pattern=DIGEST)
    finding_policy_id: str = Field(pattern=STABLE_ID)
    finding_policy_digest: str = Field(pattern=DIGEST)
    findings: tuple[RecommendationHumanReviewFindingItemInput, ...] = Field(
        min_length=1, max_length=20
    )
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_evidence_was_reviewed: bool
    acknowledged_finding_is_not_a_review_decision: bool


class RecommendationHumanReviewFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_packet_id: str
    schema_version: str
    version: int
    source_lease_id: str
    source_presentation_id: str
    source_presentation_digest: str
    source_assignment_set_id: str
    recommendation_id: str
    readiness_assessment_id: str
    promotion_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    classification: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_code: str
    finding_count: int
    finding_bytes: int
    finding_content_digest: str
    finding_metadata_digest: str
    lineage_digest: str
    category_catalog_digest: str
    severity_catalog_digest: str
    finding_policy_id: str
    finding_policy_digest: str
    finding_policy_version: str
    recorder_id: str
    created_at: datetime
    expires_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    human_findings_recorded: bool
    technical_finding_recorded: bool
    service_impact_finding_recorded: bool
    exact_assignee_verified: bool
    browser_session_bound: bool
    source_integrity_verified: bool
    immutable_finding_confirmed: bool
    encrypted_at_rest: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    human_review_completed: bool
    recommendation_approved: bool
    correction_created: bool
    workflow_created: bool
    itsm_record_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool

    @classmethod
    def from_record(
        cls, record: RecommendationHumanReviewFindingRecord
    ) -> RecommendationHumanReviewFindingData:
        return cls.model_validate({field: getattr(record, field) for field in cls.model_fields})


class RecommendationHumanReviewFindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: RecommendationHumanReviewFindingData
    meta: ResponseMeta
