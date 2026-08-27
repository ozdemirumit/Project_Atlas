from __future__ import annotations

import base64
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.document_knowledge import (
    DocumentKnowledgeDraft,
    DocumentKnowledgeFinalApproval,
    DocumentKnowledgePublicationPreparation,
    DocumentKnowledgeReviewDecision,
)

_STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
_MEDIA_TYPE = r"^[a-z]+/[a-z0-9.+-]+$"


class DocumentKnowledgeDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_base64: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    draft_domain: str = Field(pattern=_STABLE_ID)
    content_type: str = Field(pattern=_MEDIA_TYPE)
    classification: str = Field(pattern=_STABLE_ID)
    access_policy_id: str = Field(pattern=_STABLE_ID)
    retention_policy_id: str = Field(pattern=_STABLE_ID)
    purpose: str = Field(min_length=20, max_length=1000)

    @field_validator("content_base64")
    @classmethod
    def _decodable(cls, value: str) -> str:
        try:
            base64.b64decode(value, validate=True)
        except Exception as exc:
            raise ValueError("content_base64 must be valid base64") from exc
        return value

    def content_bytes(self) -> bytes:
        return base64.b64decode(self.content_base64, validate=True)


class DocumentKnowledgeReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str = Field(pattern=_STABLE_ID)
    decision: str
    findings: list[str] = Field(min_length=1, max_length=20)


class DocumentKnowledgeApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str = Field(pattern=_STABLE_ID)
    decision: str
    rationale: str = Field(min_length=20, max_length=1000)


class DocumentKnowledgePublicationPreparationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str = Field(pattern=_STABLE_ID)
    chunking_profile_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class DocumentKnowledgeDraftData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    organization_id: str
    environment_id: str
    knowledge_item_id: str
    title: str
    draft_domain: str
    content_type: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    protected_material_digest: str
    byte_count: int
    created_at: datetime
    instance_state: str
    canonical_digest: str

    @classmethod
    def from_domain(cls, draft: DocumentKnowledgeDraft) -> DocumentKnowledgeDraftData:
        return cls.model_validate(draft, from_attributes=True)


class DocumentKnowledgeReviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    draft_id: str
    organization_id: str
    environment_id: str
    decision: str
    findings: list[str]
    decided_at: datetime
    instance_state: str
    canonical_digest: str

    @classmethod
    def from_domain(cls, review: DocumentKnowledgeReviewDecision) -> DocumentKnowledgeReviewData:
        return cls.model_validate(review, from_attributes=True)


class DocumentKnowledgeApprovalData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    review_id: str
    draft_id: str
    organization_id: str
    environment_id: str
    decision: str
    rationale: str
    decided_at: datetime
    instance_state: str
    canonical_digest: str

    @classmethod
    def from_domain(cls, approval: DocumentKnowledgeFinalApproval) -> DocumentKnowledgeApprovalData:
        return cls.model_validate(approval, from_attributes=True)


class DocumentKnowledgePublicationPreparationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preparation_id: str
    approval_id: str
    draft_id: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    protected_material_digest: str
    chunking_profile_digest: str
    prepared_at: datetime
    instance_state: str
    canonical_digest: str

    @classmethod
    def from_domain(
        cls, preparation: DocumentKnowledgePublicationPreparation
    ) -> DocumentKnowledgePublicationPreparationData:
        return cls.model_validate(preparation, from_attributes=True)


class DocumentKnowledgeDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DocumentKnowledgeDraftData
    meta: ResponseMeta


class DocumentKnowledgeReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DocumentKnowledgeReviewData
    meta: ResponseMeta


class DocumentKnowledgeApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DocumentKnowledgeApprovalData
    meta: ResponseMeta


class DocumentKnowledgePublicationPreparationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DocumentKnowledgePublicationPreparationData
    meta: ResponseMeta
