from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.source_materialization import (
    OperationalKnowledgeSourceMaterializationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeSourceMaterializationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-source-materialization-input.v1",
        pattern=STABLE_ID,
    )
    publication_preparation_digest: str = Field(pattern=DIGEST)
    materialization_policy_id: str = Field(pattern=STABLE_ID)
    materialization_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_immutable_approved_source: bool
    acknowledged_protected_content_boundary: bool
    acknowledged_no_chunking_or_operational_authority: bool


class OperationalKnowledgeSourceMaterializationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    materialization_id: str
    schema_version: str
    version: int
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
    materialization_policy_id: str
    materialization_policy_digest: str
    materialization_policy_version: str
    canonicalization_profile_id: str
    canonicalization_profile_digest: str
    source_security_profile_id: str
    source_security_profile_digest: str
    materializer_id: str
    materialization_receipt_digest: str
    source_artifact_digest: str
    protected_material_digest: str
    media_type: str
    source_bytes: int
    canonical_bytes: int
    canonical_characters: int
    security_scan_evidence_digest: str
    governance_binding_digest: str
    materialized_at: datetime
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
        cls, record: OperationalKnowledgeSourceMaterializationRecord
    ) -> OperationalKnowledgeSourceMaterializationData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeSourceMaterializationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeSourceMaterializationData
    meta: ResponseMeta
