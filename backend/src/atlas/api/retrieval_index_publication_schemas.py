from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.retrieval_index_publication import (
    OperationalKnowledgeRetrievalPublicationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeRetrievalPublicationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-retrieval-publication-input.v1", pattern=STABLE_ID
    )
    index_staging_digest: str = Field(pattern=DIGEST)
    publication_policy_id: str = Field(pattern=STABLE_ID)
    publication_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_policy_filtered_visibility: bool
    acknowledged_no_vector_store_disclosure: bool
    acknowledged_no_context_or_operational_authority: bool


class OperationalKnowledgeRetrievalPublicationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_id: str
    schema_version: str
    version: int
    index_staging_id: str
    index_staging_digest: str
    embedding_set_id: str
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
    publication_policy_id: str
    publication_policy_digest: str
    publication_policy_version: str
    publication_profile_id: str
    publication_profile_digest: str
    retrieval_route_profile_digest: str
    publisher_id: str
    publication_receipt_digest: str
    index_profile_digest: str
    staging_boundary_digest: str
    authorization_payload_profile_digest: str
    model_profile_digest: str
    governance_binding_digest: str
    projection_manifest_digest: str
    point_coverage_digest: str
    authorization_metadata_validation_digest: str
    reconciliation_digest: str
    route_generation_digest: str
    activation_digest: str
    route_verification_digest: str
    authorization_enforcement_digest: str
    lifecycle_filter_digest: str
    rollback_metadata_digest: str
    published_at: datetime
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
        cls, record: OperationalKnowledgeRetrievalPublicationRecord
    ) -> OperationalKnowledgeRetrievalPublicationData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeRetrievalPublicationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeRetrievalPublicationData
    meta: ResponseMeta
