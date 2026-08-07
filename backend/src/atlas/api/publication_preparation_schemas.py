from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.publication_preparation import (
    OperationalKnowledgePublicationPreparationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgePublicationPreparationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-publication-preparation-input.v1",
        pattern=STABLE_ID,
    )
    final_resolution_digest: str = Field(pattern=DIGEST)
    preparation_policy_id: str = Field(pattern=STABLE_ID)
    preparation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_immutable_approved_generation: bool
    acknowledged_metadata_only_preparation: bool
    acknowledged_no_processing_or_operational_authority: bool


class OperationalKnowledgePublicationPreparationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preparation_id: str
    schema_version: str
    version: int
    resolution_id: str
    resolution_digest: str
    review_request_id: str
    review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    preparation_policy_id: str
    preparation_policy_digest: str
    preparation_policy_version: str
    preparation_profile_id: str
    preparation_profile_digest: str
    chunking_profile_id: str
    chunking_profile_digest: str
    embedding_profile_id: str
    embedding_profile_digest: str
    index_profile_id: str
    index_profile_digest: str
    validation_profile_id: str
    validation_profile_digest: str
    preparer_id: str
    preparation_receipt_digest: str
    source_artifact_digest: str
    metadata_manifest_digest: str
    access_manifest_digest: str
    retention_manifest_digest: str
    prepared_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_approved: bool
    publication_ready: bool
    publication_prepared: bool
    knowledge_published: bool
    chunks_created: bool
    embeddings_created: bool
    index_staged: bool
    index_validated: bool
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
        cls, record: OperationalKnowledgePublicationPreparationRecord
    ) -> OperationalKnowledgePublicationPreparationData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgePublicationPreparationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgePublicationPreparationData
    meta: ResponseMeta
