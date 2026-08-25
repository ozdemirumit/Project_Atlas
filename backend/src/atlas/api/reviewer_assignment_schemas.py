from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.application.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentClaimStatus,
    OperationalKnowledgeReviewerAssignmentOption,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeReviewerAssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.operational-knowledge-reviewer-assignment-input.v1"] = (
        "atlas.operational-knowledge-reviewer-assignment-input.v1"
    )
    source_review_request_id: str = Field(pattern=STABLE_ID)
    assignment_option_id: str = Field(pattern=STABLE_ID)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_assignment_opens_no_content_and_records_no_decision: bool


class OperationalKnowledgeReviewerAssignmentInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_set_id: str = Field(pattern=STABLE_ID)
    schema_version: Literal["atlas.operational-knowledge-reviewer-assignment.v1"]
    version: Literal[1]
    source_review_request_id: str = Field(pattern=STABLE_ID)
    source_review_request_digest: str = Field(pattern=DIGEST)
    source_draft_id: str = Field(pattern=STABLE_ID)
    source_draft_digest: str = Field(pattern=DIGEST)
    knowledge_item_id: str = Field(pattern=STABLE_ID)
    draft_version_id: str = Field(pattern=STABLE_ID)
    connector_id: str = Field(pattern=STABLE_ID)
    instance_id: str = Field(pattern=STABLE_ID)
    capability_id: str = Field(pattern=STABLE_ID)
    title: str = Field(min_length=1, max_length=512)
    knowledge_lifecycle: Literal["reviewer_assigned"]
    classification: str = Field(pattern=STABLE_ID)
    retention_policy_id: str = Field(pattern=STABLE_ID)
    domain_track_code: Literal["review-track.domain"]
    security_track_code: Literal["review-track.security"]
    domain_status: Literal["assigned"]
    security_status: Literal["assigned"]
    assignment_policy_id: str = Field(pattern=STABLE_ID)
    assignment_policy_digest: str = Field(pattern=DIGEST)
    assignment_policy_version: str = Field(min_length=1, max_length=64)
    created_at: datetime
    expires_at: datetime
    instance_state: Literal["operational_knowledge_reviewers_assigned"]
    canonical_digest: str = Field(pattern=DIGEST)
    review_requested: Literal[True]
    reviewer_assigned: Literal[True]
    immutable_assignments_confirmed: Literal[True]
    encrypted_identity_references: Literal[True]
    transient_identity_buffers_erased: Literal[True]
    directory_channel_closed: Literal[True]
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

    @model_validator(mode="after")
    def validate_expiry(self) -> OperationalKnowledgeReviewerAssignmentInventoryData:
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        return self

    @classmethod
    def from_domain(
        cls, record: OperationalKnowledgeReviewerAssignmentRecord
    ) -> OperationalKnowledgeReviewerAssignmentInventoryData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeReviewerAssignmentInventoryItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeReviewerAssignmentInventoryData
    meta: ResponseMeta


class OperationalKnowledgeReviewerAssignmentClaimStatusData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_set_id: str = Field(pattern=STABLE_ID)
    schema_version: Literal["atlas.operational-knowledge-reviewer-assignment-claim-status.v1"]
    source_review_request_id: str = Field(pattern=STABLE_ID)
    source_review_request_digest: str = Field(pattern=DIGEST)
    claimed_at: datetime
    claim_state: Literal["claim_consumed_unresolved"]
    claim_consumed: Literal[True]
    assignment_completed: Literal[False]
    automatic_retry_allowed: Literal[False]
    content_inspection_opened: Literal[False]
    knowledge_approved: Literal[False]
    knowledge_published: Literal[False]
    workflow_continued: Literal[False]
    execution_authorized: Literal[False]
    deployment_approved: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_application(
        cls, status: OperationalKnowledgeReviewerAssignmentClaimStatus
    ) -> OperationalKnowledgeReviewerAssignmentClaimStatusData:
        return cls.model_validate(status, from_attributes=True)


class OperationalKnowledgeReviewerAssignmentInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[
        OperationalKnowledgeReviewerAssignmentInventoryData
        | OperationalKnowledgeReviewerAssignmentClaimStatusData,
        ...,
    ]
    meta: ResponseMeta


class OperationalKnowledgeReviewerAssignmentOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_option_id: str = Field(pattern=STABLE_ID)
    source_review_request_id: str = Field(pattern=STABLE_ID)
    source_review_request_digest: str = Field(pattern=DIGEST)
    source_draft_id: str = Field(pattern=STABLE_ID)
    knowledge_item_id: str = Field(pattern=STABLE_ID)
    connector_id: str = Field(pattern=STABLE_ID)
    instance_id: str = Field(pattern=STABLE_ID)
    capability_id: str = Field(pattern=STABLE_ID)
    assignment_policy_id: str = Field(pattern=STABLE_ID)
    assignment_policy_digest: str = Field(pattern=DIGEST)
    assignment_policy_version: str = Field(min_length=1, max_length=64)
    assignment_policy_expires_at: datetime
    required_assurance_level: Literal["single_factor", "multi_factor", "hardware_backed"]
    domain_track_code: Literal["review-track.domain"]
    security_track_code: Literal["review-track.security"]
    assignment_ttl_minutes: int = Field(ge=5, le=10_080)
    resulting_instance_state: Literal["operational_knowledge_reviewers_assigned"] = (
        "operational_knowledge_reviewers_assigned"
    )
    resulting_domain_status: Literal["assigned"] = "assigned"
    resulting_security_status: Literal["assigned"] = "assigned"
    irreversible_claim_required: Literal[True] = True
    automatic_retry_allowed: Literal[False] = False
    review_requested: Literal[True] = True
    reviewer_assigned: Literal[True] = True
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
        cls, option: OperationalKnowledgeReviewerAssignmentOption
    ) -> OperationalKnowledgeReviewerAssignmentOptionData:
        return cls.model_validate(option, from_attributes=True)


class OperationalKnowledgeReviewerAssignmentOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[OperationalKnowledgeReviewerAssignmentOptionData, ...]
    meta: ResponseMeta


OperationalKnowledgeReviewerAssignmentData = OperationalKnowledgeReviewerAssignmentInventoryData
OperationalKnowledgeReviewerAssignmentResponse = (
    OperationalKnowledgeReviewerAssignmentInventoryItemResponse
)
