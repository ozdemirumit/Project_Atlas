from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.protected_inspection import (
    OperationalKnowledgeProtectedInspectionRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeProtectedInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-protected-inspection-input.v1",
        pattern=STABLE_ID,
    )
    source_assignment_set_id: str = Field(pattern=STABLE_ID)
    source_assignment_set_digest: str = Field(pattern=DIGEST)
    track_code: str = Field(pattern=r"^review-track\.(domain|security)$")
    inspection_policy_id: str = Field(pattern=STABLE_ID)
    inspection_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_lease_returns_no_content_and_records_no_decision: bool


class OperationalKnowledgeProtectedInspectionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_id: str
    schema_version: str
    version: int
    source_assignment_set_id: str
    source_assignment_set_digest: str
    organization_id: str
    environment_id: str
    review_request_id: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    draft_version_id: str
    source_ingestion_id: str
    source_invocation_id: str
    connector_id: str
    instance_id: str
    capability_id: str
    title: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
    manifest_id: str
    manifest_digest: str
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
    instance_state: str
    purpose: str
    canonical_digest: str
    review_requested: bool
    reviewer_assigned: bool
    content_inspection_opened: bool
    content_disclosed: bool
    content_bytes_read: int
    exact_assignee_verified: bool
    browser_session_bound: bool
    non_transferable: bool
    refresh_disabled: bool
    plaintext_secret_buffer_erased: bool
    broker_channel_closed: bool
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
    def from_domain(
        cls, record: OperationalKnowledgeProtectedInspectionRecord
    ) -> OperationalKnowledgeProtectedInspectionData:
        safe = {
            field: getattr(record, field) for field in cls.model_fields if hasattr(record, field)
        }
        return cls.model_validate(safe)


class OperationalKnowledgeProtectedInspectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeProtectedInspectionData
    meta: ResponseMeta
