from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.correction_resubmission import (
    OperationalKnowledgeCorrectionRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"
StableId = Annotated[str, Field(pattern=STABLE_ID)]
Digest = Annotated[str, Field(pattern=DIGEST)]


class OperationalKnowledgeCorrectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-correction-input.v1", pattern=STABLE_ID
    )
    source_review_request_digest: str = Field(pattern=DIGEST)
    source_decision_ids: tuple[StableId, StableId]
    source_decision_digests: tuple[Digest, Digest]
    correction_submission_id: str = Field(pattern=STABLE_ID)
    correction_submission_digest: str = Field(pattern=DIGEST)
    correction_policy_id: str = Field(pattern=STABLE_ID)
    correction_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_exact_change_requirements_addressed: bool
    acknowledged_new_immutable_review_generation: bool
    acknowledged_no_approval_or_operational_authority: bool


class OperationalKnowledgeCorrectionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correction_id: str
    schema_version: str
    version: int
    source_review_request_id: str
    source_review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    source_decision_ids: tuple[str, str]
    source_decision_digests: tuple[str, str]
    decision_aggregate_digest: str
    organization_id: str
    environment_id: str
    knowledge_item_id: str
    prior_draft_version_id: str
    title: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
    correction_submission_id: str
    correction_submission_digest: str
    correction_policy_id: str
    correction_policy_digest: str
    correction_policy_version: str
    adapter_id: str
    attestation_digest: str
    new_draft_id: str
    new_draft_version_id: str
    new_draft_schema_version: str
    new_draft_content_digest: str
    new_draft_metadata_digest: str
    new_provenance_digest: str
    new_draft_item_count: int
    new_draft_bytes: int
    new_review_request_id: str
    new_manifest_id: str
    new_manifest_schema_version: str
    new_manifest_digest: str
    new_routing_digest: str
    new_governance_digest: str
    domain_track_code: str
    security_track_code: str
    domain_status: str
    security_status: str
    review_generation: int
    manifest_bytes: int
    created_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    correction_created: bool
    corrected_draft_created: bool
    review_resubmitted: bool
    immutable_draft_confirmed: bool
    immutable_manifest_confirmed: bool
    encrypted_at_rest: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    reviewer_assigned: bool
    content_inspection_opened: bool
    domain_review_completed: bool
    security_review_completed: bool
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
        cls, record: OperationalKnowledgeCorrectionRecord
    ) -> OperationalKnowledgeCorrectionData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeCorrectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeCorrectionData
    meta: ResponseMeta
