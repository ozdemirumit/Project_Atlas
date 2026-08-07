from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.review_finding import (
    OperationalKnowledgeReviewFindingRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeReviewFindingItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_code: str = Field(pattern=STABLE_ID)
    severity_code: str = Field(pattern=STABLE_ID)
    summary: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=4000)


class OperationalKnowledgeReviewFindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-review-finding-input.v1", pattern=STABLE_ID
    )
    source_presentation_digest: str = Field(pattern=DIGEST)
    finding_policy_id: str = Field(pattern=STABLE_ID)
    finding_policy_digest: str = Field(pattern=DIGEST)
    findings: tuple[OperationalKnowledgeReviewFindingItemInput, ...] = Field(
        min_length=1, max_length=20
    )
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_evidence_was_reviewed: bool
    acknowledged_finding_is_not_a_review_decision: bool


class OperationalKnowledgeReviewFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_packet_id: str
    schema_version: str
    version: int
    source_lease_id: str
    source_presentation_id: str
    source_presentation_digest: str
    source_assignment_set_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    source_draft_id: str
    knowledge_item_id: str
    draft_version_id: str
    connector_id: str
    instance_id: str
    capability_id: str
    title: str
    classification: str
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
    instance_state: str
    purpose: str
    canonical_digest: str
    finding_recorded: bool
    domain_finding_recorded: bool
    security_finding_recorded: bool
    exact_assignee_verified: bool
    browser_session_bound: bool
    source_integrity_verified: bool
    immutable_finding_confirmed: bool
    encrypted_at_rest: bool
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
    def from_record(
        cls, record: OperationalKnowledgeReviewFindingRecord
    ) -> OperationalKnowledgeReviewFindingData:
        return cls.model_validate({field: getattr(record, field) for field in cls.model_fields})


class OperationalKnowledgeReviewFindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeReviewFindingData
    meta: ResponseMeta
