from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.application.draft_review_request import (
    OperationalKnowledgeReviewRequestOption,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"


class OperationalKnowledgeReviewRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.operational-knowledge-review-request-input.v1"] = (
        "atlas.operational-knowledge-review-request-input.v1"
    )
    source_draft_id: str = Field(pattern=STABLE_ID)
    review_request_option_id: str = Field(pattern=STABLE_ID)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_result_is_only_an_unassigned_review_request: bool


class OperationalKnowledgeReviewRequestInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_request_id: str
    schema_version: str
    version: int
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    draft_version_id: str
    connector_id: str
    instance_id: str
    capability_id: str
    title: str
    knowledge_lifecycle: Literal["review_requested"]
    classification: str
    retention_policy_id: str
    retention_policy_digest: str
    orchestration_policy_id: str
    orchestration_policy_digest: str
    orchestration_policy_version: str
    domain_track_code: str
    security_track_code: str
    assignment_strategy: str
    sla_class: str
    domain_status: Literal["awaiting_reviewer"]
    security_status: Literal["awaiting_reviewer"]
    manifest_bytes: int
    created_at: datetime
    instance_state: Literal["operational_knowledge_review_requested"]
    canonical_digest: str
    review_requested: Literal[True]
    immutable_manifest_confirmed: Literal[True]
    encrypted_at_rest: Literal[True]
    transient_buffers_erased: Literal[True]
    artifact_channel_closed: Literal[True]
    reviewer_assigned: Literal[False]
    content_inspection_opened: Literal[False]
    domain_review_completed: Literal[False]
    security_review_completed: Literal[False]
    correction_created: Literal[False]
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
        cls, record: OperationalKnowledgeReviewRequestRecord
    ) -> OperationalKnowledgeReviewRequestInventoryData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeReviewRequestInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[OperationalKnowledgeReviewRequestInventoryData, ...]
    meta: ResponseMeta


class OperationalKnowledgeReviewRequestInventoryItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeReviewRequestInventoryData
    meta: ResponseMeta


class OperationalKnowledgeReviewRequestOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_request_option_id: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    connector_id: str
    instance_id: str
    capability_id: str
    orchestration_policy_id: str
    orchestration_policy_digest: str
    orchestration_policy_version: str
    orchestration_policy_expires_at: datetime
    required_assurance_level: Literal["single_factor", "multi_factor", "hardware_backed"]
    classification: str
    retention_policy_id: str
    domain_track_code: str
    security_track_code: str
    assignment_strategy: str
    sla_class: str
    resulting_instance_state: Literal["operational_knowledge_review_requested"] = (
        "operational_knowledge_review_requested"
    )
    resulting_domain_status: Literal["awaiting_reviewer"] = "awaiting_reviewer"
    resulting_security_status: Literal["awaiting_reviewer"] = "awaiting_reviewer"
    irreversible_claim_required: Literal[True] = True
    automatic_retry_allowed: Literal[False] = False
    review_requested: Literal[True] = True
    reviewer_assigned: Literal[False] = False
    content_inspection_opened: Literal[False] = False
    domain_review_completed: Literal[False] = False
    security_review_completed: Literal[False] = False
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
        cls, option: OperationalKnowledgeReviewRequestOption
    ) -> OperationalKnowledgeReviewRequestOptionData:
        return cls.model_validate(option, from_attributes=True)


class OperationalKnowledgeReviewRequestOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[OperationalKnowledgeReviewRequestOptionData, ...]
    meta: ResponseMeta
