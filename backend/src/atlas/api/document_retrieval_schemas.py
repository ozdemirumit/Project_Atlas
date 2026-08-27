from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.document_retrieval import DocumentKnowledgeSearchResult

_STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"


class DocumentKnowledgeIndexInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preparation_id: str = Field(pattern=_STABLE_ID)


class DocumentKnowledgeIndexData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preparation_id: str
    chunk_count: int


class DocumentKnowledgeIndexResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DocumentKnowledgeIndexData
    meta: ResponseMeta


class DocumentKnowledgeSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)


class DocumentKnowledgeSearchResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    knowledge_item_id: str
    content_digest: str
    score: float
    excerpt: str

    @classmethod
    def from_domain(
        cls, result: DocumentKnowledgeSearchResult
    ) -> DocumentKnowledgeSearchResultData:
        return cls.model_validate(result, from_attributes=True)


class DocumentKnowledgeSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[DocumentKnowledgeSearchResultData]
    meta: ResponseMeta
