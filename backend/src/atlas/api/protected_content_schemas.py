from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentGrant,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeProtectedContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-protected-content-input.v1", pattern=STABLE_ID
    )
    source_lease_digest: str = Field(pattern=DIGEST)
    presentation_policy_id: str = Field(pattern=STABLE_ID)
    presentation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_sensitive_read_only_content_grants_no_review_authority: bool


class OperationalKnowledgeProtectedContentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presentation_id: str
    schema_version: str
    version: int
    source_lease_id: str
    source_lease_digest: str
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
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
    track_code: str
    output_media_type: str
    language: str
    content: str
    presented_content_digest: str
    content_bytes: int
    redaction_digest: str
    truncation_digest: str
    cleanup_digest: str
    presentation_policy_id: str
    presentation_policy_digest: str
    presentation_policy_version: str
    presenter_id: str
    presented_at: datetime
    expires_at: datetime
    instance_state: str
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
    artifact_channel_closed: bool
    domain_review_completed: bool
    security_review_completed: bool
    correction_created: bool
    knowledge_approved: bool
    knowledge_published: bool
    chunks_created: bool
    embeddings_created: bool
    retrieval_published: bool
    model_context_available: bool
    graph_updated: bool
    scheduled: bool
    workflow_continued: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_grant(
        cls, grant: OperationalKnowledgeProtectedContentGrant
    ) -> OperationalKnowledgeProtectedContentData:
        record = grant.record
        safe = {
            field: getattr(record, field) for field in cls.model_fields if hasattr(record, field)
        }
        safe["content"] = grant.content
        return cls.model_validate(safe)


class OperationalKnowledgeProtectedContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeProtectedContentData
    meta: ResponseMeta
