from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeReviewerAssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-reviewer-assignment-input.v1", pattern=STABLE_ID
    )
    source_review_request_id: str = Field(pattern=STABLE_ID)
    source_review_request_digest: str = Field(pattern=DIGEST)
    assignment_policy_id: str = Field(pattern=STABLE_ID)
    assignment_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_assignment_opens_no_content_and_records_no_decision: bool


class OperationalKnowledgeReviewerAssignmentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_set_id: str
    schema_version: str
    version: int
    claim_id: str
    source_review_request_id: str
    source_review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    organization_id: str
    environment_id: str
    knowledge_item_id: str
    draft_version_id: str
    source_ingestion_id: str
    source_invocation_id: str
    connector_id: str
    instance_id: str
    capability_id: str
    title: str
    knowledge_lifecycle: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
    manifest_id: str
    manifest_digest: str
    domain_assignment_id: str
    security_assignment_id: str
    domain_reviewer_subject_digest: str
    security_reviewer_subject_digest: str
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    domain_status: str
    security_status: str
    assignment_digest: str
    routing_digest: str
    eligibility_digest: str
    separation_digest: str
    artifact_digest: str
    assignment_policy_id: str
    assignment_policy_digest: str
    assignment_policy_version: str
    assignment_adapter_id: str
    created_at: datetime
    expires_at: datetime
    instance_state: str
    requested_by: str
    purpose: str
    canonical_digest: str
    review_requested: bool
    reviewer_assigned: bool
    immutable_assignments_confirmed: bool
    encrypted_identity_references: bool
    transient_identity_buffers_erased: bool
    directory_channel_closed: bool
    content_inspection_opened: bool
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
        cls, record: OperationalKnowledgeReviewerAssignmentRecord
    ) -> OperationalKnowledgeReviewerAssignmentData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeReviewerAssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeReviewerAssignmentData
    meta: ResponseMeta
