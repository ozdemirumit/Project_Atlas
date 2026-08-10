from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.protected_content import (
    RecommendationProtectedContentGrant,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class RecommendationProtectedContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.recommendation-protected-content-input.v1", pattern=STABLE_ID
    )
    source_lease_digest: str = Field(pattern=DIGEST)
    presentation_policy_id: str = Field(pattern=STABLE_ID)
    presentation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_sensitive_read_only_content: bool
    acknowledged_no_finding_decision_approval_or_operational_authority: bool


class RecommendationProtectedContentData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation_id: str
    schema_version: str
    version: int
    source_lease_id: str
    source_assignment_set_id: str
    recommendation_id: str
    review_request_id: str
    readiness_assessment_id: str
    promotion_id: str
    organization_id: str
    environment_id: str
    classification: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_code: str
    opaque_assignment_id: str
    output_media_type: str
    language: str
    content: str
    presented_content_digest: str
    protected_content_bytes_returned: int
    redaction_digest: str
    truncation_digest: str
    cleanup_digest: str
    presentation_policy_id: str
    presentation_policy_digest: str
    presentation_policy_version: str
    presenter_id: str
    presented_at: datetime
    expires_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    review_requested: bool
    reviewer_assigned: bool
    content_inspection_opened: bool
    content_disclosed: bool
    exact_assignee_verified: bool
    browser_session_bound: bool
    source_integrity_verified: bool
    redaction_applied: bool
    truncated: bool
    active_content_rejected: bool
    transient_buffers_erased: bool
    presenter_channel_closed: bool
    human_findings_recorded: bool
    human_review_completed: bool
    recommendation_approved: bool
    workflow_created: bool
    itsm_record_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool

    @classmethod
    def from_grant(
        cls, grant: RecommendationProtectedContentGrant
    ) -> RecommendationProtectedContentData:
        record = grant.record
        safe = {
            field: getattr(record, field) for field in cls.model_fields if hasattr(record, field)
        }
        safe["content"] = grant.content
        return cls.model_validate(safe)


class RecommendationProtectedContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RecommendationProtectedContentData
    meta: ResponseMeta
