from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.embedding_generation import (
    OperationalKnowledgeEmbeddingRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeEmbeddingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-embedding-input.v1", pattern=STABLE_ID
    )
    chunk_set_digest: str = Field(pattern=DIGEST)
    embedding_policy_id: str = Field(pattern=STABLE_ID)
    embedding_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_protected_chunk_boundary: bool
    acknowledged_immutable_model_profile: bool
    acknowledged_no_index_or_operational_authority: bool


class OperationalKnowledgeEmbeddingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    embedding_set_id: str
    schema_version: str
    version: int
    chunk_set_id: str
    chunk_set_digest: str
    materialization_id: str
    preparation_id: str
    resolution_id: str
    review_request_id: str
    source_draft_id: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    embedding_policy_id: str
    embedding_policy_digest: str
    embedding_policy_version: str
    model_profile_id: str
    model_profile_digest: str
    model_artifact_digest: str
    tokenizer_profile_digest: str
    vector_dimension: int
    normalization_profile_id: str
    distance_metric_id: str
    data_boundary_id: str
    data_boundary_digest: str
    embedder_id: str
    embedding_receipt_digest: str
    protected_material_digest: str
    ordered_chunk_manifest_digest: str
    chunking_profile_digest: str
    governance_binding_digest: str
    embedding_count: int
    vector_manifest_digest: str
    chunk_vector_binding_digest: str
    numeric_validation_digest: str
    coverage_validation_digest: str
    resource_evidence_digest: str
    embedded_at: datetime
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
        cls, record: OperationalKnowledgeEmbeddingRecord
    ) -> OperationalKnowledgeEmbeddingData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeEmbeddingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeEmbeddingData
    meta: ResponseMeta
