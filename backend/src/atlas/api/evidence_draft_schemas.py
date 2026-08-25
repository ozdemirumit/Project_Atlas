from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.application.evidence_draft import (
    OperationalEvidenceKnowledgeDraftOption,
)
from atlas.modules.knowledge.domain.evidence_draft import (
    OperationalEvidenceKnowledgeDraftRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"


class OperationalEvidenceKnowledgeDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.operational-evidence-knowledge-draft-input.v1"] = (
        "atlas.operational-evidence-knowledge-draft-input.v1"
    )
    source_ingestion_id: str = Field(pattern=STABLE_ID)
    curation_option_id: str = Field(pattern=STABLE_ID)
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


class OperationalEvidenceKnowledgeDraftInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    schema_version: str
    version: int
    source_ingestion_id: str
    source_ingestion_digest: str
    evidence_package_id: str
    connector_id: str
    instance_id: str
    capability_id: str
    title: str
    knowledge_lifecycle: Literal["draft"]
    classification: str
    retention_policy_id: str
    retention_policy_digest: str
    curation_policy_id: str
    curation_policy_digest: str
    curation_policy_version: str
    draft_item_count: int
    draft_bytes: int
    observed_from: datetime
    observed_to: datetime
    created_at: datetime
    instance_state: Literal["draft_operational_knowledge_created"]
    canonical_digest: str
    evidence_ingested: Literal[True]
    knowledge_item_created: Literal[True]
    immutable_draft_confirmed: Literal[True]
    encrypted_at_rest: Literal[True]
    transient_buffers_erased: Literal[True]
    artifact_channel_closed: Literal[True]
    domain_review_completed: Literal[False]
    security_review_completed: Literal[False]
    review_requested: Literal[False] = False
    knowledge_approved: Literal[False]
    knowledge_published: Literal[False]
    chunks_created: Literal[False]
    embeddings_created: Literal[False]
    retrieval_published: Literal[False]
    model_context_available: Literal[False]
    graph_updated: Literal[False]
    scheduled: Literal[False]
    workflow_continued: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]
    reused: bool

    @classmethod
    def from_domain(
        cls, record: OperationalEvidenceKnowledgeDraftRecord
    ) -> OperationalEvidenceKnowledgeDraftInventoryData:
        return cls.model_validate(record, from_attributes=True)


class OperationalEvidenceKnowledgeDraftInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[OperationalEvidenceKnowledgeDraftInventoryData, ...]
    meta: ResponseMeta


class OperationalEvidenceKnowledgeDraftInventoryItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalEvidenceKnowledgeDraftInventoryData
    meta: ResponseMeta


class OperationalEvidenceKnowledgeDraftOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curation_option_id: str
    source_ingestion_id: str
    source_ingestion_digest: str
    evidence_package_id: str
    capability_id: str
    curation_policy_id: str
    curation_policy_digest: str
    curation_policy_version: str
    curation_policy_expires_at: datetime
    required_assurance_level: Literal["single_factor", "multi_factor", "hardware_backed"]
    classification: str
    access_policy_id: str
    retention_policy_id: str
    maximum_draft_items: int
    maximum_draft_bytes: int
    resulting_instance_state: Literal["draft_operational_knowledge_created"] = (
        "draft_operational_knowledge_created"
    )
    irreversible_claim_required: Literal[True] = True
    automatic_retry_allowed: Literal[False] = False
    review_requested: Literal[False] = False
    knowledge_approved: Literal[False] = False
    knowledge_published: Literal[False] = False
    retrieval_published: Literal[False] = False
    model_context_available: Literal[False] = False
    scheduled: Literal[False] = False
    workflow_continued: Literal[False] = False
    execution_authorized: Literal[False] = False
    deployment_approved: Literal[False] = False
    infrastructure_mutation_performed: Literal[False] = False

    @classmethod
    def from_application(
        cls, option: OperationalEvidenceKnowledgeDraftOption
    ) -> OperationalEvidenceKnowledgeDraftOptionData:
        return cls.model_validate(option, from_attributes=True)


class OperationalEvidenceKnowledgeDraftOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[OperationalEvidenceKnowledgeDraftOptionData, ...]
    meta: ResponseMeta
