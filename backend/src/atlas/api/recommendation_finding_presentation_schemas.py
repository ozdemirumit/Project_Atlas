from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.finding_presentation import (
    RecommendationFindingPresentationGrant,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class RecommendationFindingPresentationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.recommendation-finding-presentation-input.v1",
        pattern=STABLE_ID,
    )
    source_finding_digest: str = Field(pattern=DIGEST)
    presentation_policy_id: str = Field(pattern=STABLE_ID)
    presentation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_findings_are_sensitive: bool
    acknowledged_finding_presentation_is_not_a_review_decision: bool


class RecommendationPresentedFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_code: str
    severity_code: str
    summary: str
    detail: str


class RecommendationFindingPresentationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_presentation_id: str
    schema_version: str
    version: int
    source_finding_packet_id: str
    source_finding_digest: str
    source_lease_id: str
    source_presentation_id: str
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
    findings: tuple[RecommendationPresentedFindingData, ...]
    finding_count: int
    finding_bytes: int
    finding_content_digest: str
    finding_metadata_digest: str
    lineage_digest: str
    category_catalog_digest: str
    severity_catalog_digest: str
    presentation_policy_id: str
    presentation_policy_digest: str
    presentation_policy_version: str
    presenter_id: str
    presented_at: datetime
    expires_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    human_findings_recorded: bool
    human_findings_presented: bool
    technical_finding_recorded: bool
    service_impact_finding_recorded: bool
    technical_findings_presented: bool
    service_impact_findings_presented: bool
    exact_assignee_verified: bool
    browser_session_bound: bool
    source_integrity_verified: bool
    encrypted_source_verified: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    human_review_completed: bool
    correction_created: bool
    recommendation_approved: bool
    workflow_created: bool
    itsm_record_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool

    @classmethod
    def from_grant(
        cls, grant: RecommendationFindingPresentationGrant
    ) -> RecommendationFindingPresentationData:
        values = {
            field: getattr(grant.record, field) for field in cls.model_fields if field != "findings"
        }
        values["findings"] = tuple(
            RecommendationPresentedFindingData(
                category_code=item.category_code,
                severity_code=item.severity_code,
                summary=item.summary,
                detail=item.detail,
            )
            for item in grant.findings
        )
        return cls.model_validate(values)


class RecommendationFindingPresentationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: RecommendationFindingPresentationData
    meta: ResponseMeta
