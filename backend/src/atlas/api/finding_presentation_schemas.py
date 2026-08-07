from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.finding_presentation import (
    OperationalKnowledgeFindingPresentationGrant,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeFindingPresentationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-finding-presentation-input.v1",
        pattern=STABLE_ID,
    )
    source_finding_digest: str = Field(pattern=DIGEST)
    presentation_policy_id: str = Field(pattern=STABLE_ID)
    presentation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_findings_are_sensitive: bool
    acknowledged_finding_presentation_is_not_a_review_decision: bool


class OperationalKnowledgePresentedFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_code: str
    severity_code: str
    summary: str
    detail: str


class OperationalKnowledgeFindingPresentationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_presentation_id: str
    schema_version: str
    version: int
    source_finding_packet_id: str
    source_finding_digest: str
    source_lease_id: str
    source_content_presentation_id: str
    source_assignment_set_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    source_draft_id: str
    knowledge_item_id: str
    draft_version_id: str
    title: str
    classification: str
    track_code: str
    findings: tuple[OperationalKnowledgePresentedFindingData, ...]
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
    instance_state: str
    purpose: str
    canonical_digest: str
    finding_recorded: bool
    finding_presented: bool
    domain_finding_recorded: bool
    security_finding_recorded: bool
    exact_assignee_verified: bool
    browser_session_bound: bool
    source_integrity_verified: bool
    encrypted_source_verified: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    domain_review_completed: bool
    security_review_completed: bool
    correction_created: bool
    knowledge_approved: bool
    knowledge_published: bool
    retrieval_published: bool
    model_context_available: bool
    workflow_continued: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_grant(
        cls, grant: OperationalKnowledgeFindingPresentationGrant
    ) -> OperationalKnowledgeFindingPresentationData:
        values = {
            field: getattr(grant.record, field) for field in cls.model_fields if field != "findings"
        }
        values["findings"] = tuple(
            OperationalKnowledgePresentedFindingData(
                category_code=item.category_code,
                severity_code=item.severity_code,
                summary=item.summary,
                detail=item.detail,
            )
            for item in grant.findings
        )
        return cls.model_validate(values)


class OperationalKnowledgeFindingPresentationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeFindingPresentationData
    meta: ResponseMeta
