from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.final_resolution import (
    OperationalKnowledgeFinalResolutionRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"
StableId = Annotated[str, Field(pattern=STABLE_ID)]
Digest = Annotated[str, Field(pattern=DIGEST)]


class OperationalKnowledgeFinalResolutionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-final-resolution-input.v1", pattern=STABLE_ID
    )
    review_request_digest: str = Field(pattern=DIGEST)
    decision_ids: tuple[StableId, StableId]
    decision_digests: tuple[Digest, Digest]
    disposition_code: str = Field(pattern=r"^final-resolution\.(approved|rejected)$")
    basis_codes: tuple[StableId, ...] = Field(min_length=1, max_length=8)
    resolution_policy_id: str = Field(pattern=STABLE_ID)
    resolution_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_immutable_review_generation: bool
    acknowledged_publication_readiness_only: bool
    acknowledged_no_operational_authority: bool


class OperationalKnowledgeFinalResolutionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution_id: str
    schema_version: str
    version: int
    review_request_id: str
    review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    source_assignment_set_id: str
    decision_ids: tuple[str, str]
    decision_digests: tuple[str, str]
    decision_aggregate_digest: str
    organization_id: str
    environment_id: str
    knowledge_item_id: str
    draft_version_id: str
    title: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    disposition_code: str
    basis_codes: tuple[str, ...]
    basis_digest: str
    resolution_policy_id: str
    resolution_policy_digest: str
    resolution_policy_version: str
    attestor_id: str
    attestation_digest: str
    resolved_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    domain_review_completed: bool
    security_review_completed: bool
    domain_review_passed: bool
    security_review_passed: bool
    correction_required: bool
    correction_created: bool
    knowledge_approved: bool
    publication_ready: bool
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
        cls, record: OperationalKnowledgeFinalResolutionRecord
    ) -> OperationalKnowledgeFinalResolutionData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeFinalResolutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeFinalResolutionData
    meta: ResponseMeta
