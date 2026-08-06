from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeReviewRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-review-request-input.v1", pattern=STABLE_ID
    )
    source_draft_id: str = Field(pattern=STABLE_ID)
    source_draft_digest: str = Field(pattern=DIGEST)
    orchestration_policy_id: str = Field(pattern=STABLE_ID)
    orchestration_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_result_is_only_an_unassigned_review_request: bool


class OperationalKnowledgeReviewRequestData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_request_id: str
    schema_version: str
    version: int
    claim_id: str
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
    draft_domain: str
    content_type: str
    language: str
    knowledge_lifecycle: str
    classification: str
    access_policy_id: str
    access_policy_digest: str
    retention_policy_id: str
    retention_policy_digest: str
    encryption_profile_id: str
    encryption_profile_digest: str
    draft_content_digest: str
    draft_metadata_digest: str
    provenance_digest: str
    manifest_id: str
    manifest_artifact_id: str
    manifest_schema_version: str
    manifest_digest: str
    routing_digest: str
    governance_digest: str
    artifact_digest: str
    orchestration_policy_id: str
    orchestration_policy_digest: str
    orchestration_policy_version: str
    orchestration_adapter_id: str
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    assignment_strategy: str
    sla_class: str
    domain_status: str
    security_status: str
    manifest_bytes: int
    created_at: datetime
    instance_state: str
    requested_by: str
    purpose: str
    canonical_digest: str
    review_requested: bool
    immutable_manifest_confirmed: bool
    encrypted_at_rest: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    reviewer_assigned: bool
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
        cls, record: OperationalKnowledgeReviewRequestRecord
    ) -> OperationalKnowledgeReviewRequestData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeReviewRequestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeReviewRequestData
    meta: ResponseMeta
