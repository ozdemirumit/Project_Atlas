from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.application.document_knowledge_lifecycle import (
    DocumentKnowledgeItemLifecycleView,
)
from atlas.modules.knowledge.domain.document_knowledge_lifecycle import (
    DocumentKnowledgeConflict,
    DocumentKnowledgeItemLifecycleRecord,
)

_STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"


class DocumentKnowledgeLifecycleTransitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2000)


class DocumentKnowledgeSupersessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    superseded_by_item_id: str = Field(pattern=_STABLE_ID)
    reason: str = Field(min_length=1, max_length=2000)


class DocumentKnowledgeConflictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_item_id_a: str = Field(pattern=_STABLE_ID)
    knowledge_item_id_b: str = Field(pattern=_STABLE_ID)
    conflict_type: str


class DocumentKnowledgeConflictResolutionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: str = Field(min_length=1, max_length=2000)


class DocumentKnowledgeItemLifecycleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_item_id: str
    organization_id: str
    environment_id: str
    state: str
    reason: str
    superseded_by_item_id: str | None
    updated_by: str
    updated_at: datetime
    created_at: datetime

    @classmethod
    def from_domain(
        cls, record: DocumentKnowledgeItemLifecycleRecord
    ) -> DocumentKnowledgeItemLifecycleData:
        return cls.model_validate(record, from_attributes=True)


class DocumentKnowledgeItemLifecycleViewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_item_id: str
    organization_id: str
    environment_id: str
    state: str
    reason: str | None
    superseded_by_item_id: str | None
    updated_by: str | None
    updated_at: datetime | None

    @classmethod
    def from_domain(
        cls, view: DocumentKnowledgeItemLifecycleView
    ) -> DocumentKnowledgeItemLifecycleViewData:
        return cls.model_validate(view, from_attributes=True)


class DocumentKnowledgeConflictData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    organization_id: str
    environment_id: str
    knowledge_item_id_a: str
    knowledge_item_id_b: str
    conflict_type: str
    detected_by: str
    detected_at: datetime
    resolution: str | None
    resolved_by: str | None
    resolved_at: datetime | None

    @classmethod
    def from_domain(cls, conflict: DocumentKnowledgeConflict) -> DocumentKnowledgeConflictData:
        return cls.model_validate(conflict, from_attributes=True)


class DocumentKnowledgeItemLifecycleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DocumentKnowledgeItemLifecycleData
    meta: ResponseMeta


class DocumentKnowledgeItemLifecycleViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DocumentKnowledgeItemLifecycleViewData
    meta: ResponseMeta


class DocumentKnowledgeConflictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DocumentKnowledgeConflictData
    meta: ResponseMeta


class DocumentKnowledgeConflictListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[DocumentKnowledgeConflictData]
    meta: ResponseMeta
