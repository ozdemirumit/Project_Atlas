from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.index_staging_validation import (
    OperationalKnowledgeIndexRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeIndexInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-index-input.v1", pattern=STABLE_ID
    )
    embedding_set_digest: str = Field(pattern=DIGEST)
    index_policy_id: str = Field(pattern=STABLE_ID)
    index_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_protected_vector_boundary: bool
    acknowledged_inactive_projection: bool
    acknowledged_no_publication_or_operational_authority: bool


class OperationalKnowledgeIndexData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index_staging_id: str
    schema_version: str
    version: int
    embedding_set_id: str
    embedding_set_digest: str
    chunk_set_id: str
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
    index_policy_id: str
    index_policy_digest: str
    index_policy_version: str
    index_profile_id: str
    index_profile_digest: str
    staging_boundary_id: str
    staging_boundary_digest: str
    authorization_payload_profile_digest: str
    indexer_id: str
    index_receipt_digest: str
    model_profile_digest: str
    vector_dimension: int
    normalization_profile_id: str
    distance_metric_id: str
    embedding_count: int
    vector_manifest_digest: str
    chunk_vector_binding_digest: str
    governance_binding_digest: str
    staged_point_count: int
    projection_manifest_digest: str
    point_coverage_digest: str
    authorization_metadata_validation_digest: str
    model_compatibility_validation_digest: str
    isolation_validation_digest: str
    reconciliation_digest: str
    validated_at: datetime
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
    def from_domain(cls, record: OperationalKnowledgeIndexRecord) -> OperationalKnowledgeIndexData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeIndexResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeIndexData
    meta: ResponseMeta
