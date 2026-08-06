from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.evidence_draft import (
    OperationalEvidenceKnowledgeDraftRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalEvidenceKnowledgeDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-evidence-knowledge-draft-input.v1", pattern=STABLE_ID
    )
    source_ingestion_id: str = Field(pattern=STABLE_ID)
    source_ingestion_digest: str = Field(pattern=DIGEST)
    curation_policy_id: str = Field(pattern=STABLE_ID)
    curation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_result_is_an_unapproved_non_retrievable_draft: bool


class OperationalEvidenceKnowledgeDraftData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    schema_version: str
    version: int
    claim_id: str
    source_ingestion_id: str
    source_ingestion_digest: str
    organization_id: str
    environment_id: str
    source_invocation_id: str
    evidence_package_id: str
    evidence_content_digest: str
    evidence_metadata_digest: str
    connector_id: str
    instance_id: str
    capability_id: str
    knowledge_item_id: str
    draft_version_id: str
    draft_artifact_id: str
    draft_schema_version: str
    title: str
    draft_domain: str
    content_type: str
    source_authority: str
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
    draft_access_digest: str
    draft_retention_digest: str
    curation_policy_id: str
    curation_policy_digest: str
    curation_policy_version: str
    curation_adapter_id: str
    draft_item_count: int
    draft_bytes: int
    observed_from: datetime
    observed_to: datetime
    created_at: datetime
    instance_state: str
    curated_by: str
    purpose: str
    canonical_digest: str
    evidence_ingested: bool
    knowledge_item_created: bool
    immutable_draft_confirmed: bool
    encrypted_at_rest: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
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
        cls, record: OperationalEvidenceKnowledgeDraftRecord
    ) -> OperationalEvidenceKnowledgeDraftData:
        return cls.model_validate(record, from_attributes=True)


class OperationalEvidenceKnowledgeDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalEvidenceKnowledgeDraftData
    meta: ResponseMeta
