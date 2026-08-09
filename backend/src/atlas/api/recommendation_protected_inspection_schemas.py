from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.protected_inspection import (
    RecommendationProtectedInspectionRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class RecommendationProtectedInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.recommendation-protected-inspection-input.v1", pattern=STABLE_ID
    )
    source_assignment_set_id: str = Field(pattern=STABLE_ID)
    source_assignment_set_digest: str = Field(pattern=DIGEST)
    track_code: str = Field(pattern=r"^review-track\.(technical|service-impact)$")
    opaque_assignment_id: str = Field(pattern=STABLE_ID)
    inspection_policy_id: str = Field(pattern=STABLE_ID)
    inspection_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_exact_assignee_and_track_required: bool
    acknowledged_lease_returns_no_content_or_secret_in_json: bool
    acknowledged_no_decision_approval_or_operational_authority: bool


class RecommendationProtectedInspectionData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_id: str
    schema_version: str
    version: int
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
    lease_holder_subject_digest: str
    lease_digest: str
    assignment_binding_digest: str
    policy_binding_digest: str
    cleanup_digest: str
    inspection_policy_id: str
    inspection_policy_digest: str
    inspection_policy_version: str
    lease_broker_id: str
    issued_at: datetime
    expires_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    review_requested: bool
    reviewer_assigned: bool
    content_inspection_opened: bool
    content_disclosed: bool
    protected_content_bytes_returned: int
    exact_assignee_verified: bool
    browser_session_bound: bool
    non_transferable: bool
    refresh_disabled: bool
    plaintext_secret_buffer_erased: bool
    broker_channel_closed: bool
    human_review_completed: bool
    recommendation_approved: bool
    workflow_created: bool
    itsm_record_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: RecommendationProtectedInspectionRecord
    ) -> RecommendationProtectedInspectionData:
        safe = {
            field: getattr(record, field) for field in cls.model_fields if hasattr(record, field)
        }
        return cls.model_validate(safe)


class RecommendationProtectedInspectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RecommendationProtectedInspectionData
    meta: ResponseMeta
