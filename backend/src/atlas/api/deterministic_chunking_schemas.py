from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.deterministic_chunking import (
    OperationalKnowledgeChunkingRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeChunkingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-chunking-input.v1", pattern=STABLE_ID
    )
    source_materialization_digest: str = Field(pattern=DIGEST)
    chunking_policy_id: str = Field(pattern=STABLE_ID)
    chunking_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_protected_content_boundary: bool
    acknowledged_immutable_chunking_profile: bool
    acknowledged_no_embedding_or_operational_authority: bool


class OperationalKnowledgeChunkingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_set_id: str
    schema_version: str
    version: int
    materialization_id: str
    materialization_digest: str
    preparation_id: str
    preparation_digest: str
    resolution_id: str
    resolution_digest: str
    review_request_id: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    chunking_policy_id: str
    chunking_policy_digest: str
    chunking_policy_version: str
    algorithm_profile_id: str
    algorithm_profile_digest: str
    chunker_id: str
    chunking_receipt_digest: str
    source_artifact_digest: str
    protected_material_digest: str
    chunking_profile_digest: str
    ordered_chunk_manifest_digest: str
    structure_manifest_digest: str
    governance_binding_digest: str
    determinism_evidence_digest: str
    media_type: str
    chunk_count: int
    total_chunk_characters: int
    total_chunk_tokens: int
    minimum_chunk_characters: int
    maximum_chunk_characters: int
    overlap_characters: int
    chunked_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_approved: bool
    publication_ready: bool
    publication_prepared: bool
    source_materialized: bool
    chunks_created: bool
    embeddings_created: bool
    index_staged: bool
    index_validated: bool
    knowledge_published: bool
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
        cls, record: OperationalKnowledgeChunkingRecord
    ) -> OperationalKnowledgeChunkingData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeChunkingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeChunkingData
    meta: ResponseMeta
