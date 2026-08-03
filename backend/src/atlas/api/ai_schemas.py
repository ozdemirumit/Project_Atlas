from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.ai.domain.models import GroundedAnswer


class GroundedQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=1000)
    max_results: int = Field(default=3, ge=1, le=10)


class CitationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str
    item_id: str
    item_version: str
    chunk_id: str
    title: str
    source_class: str
    source_reference: str
    location: str
    content_checksum: str
    observed_at: datetime
    classification: str


class GroundedAnswerData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_id: str
    query_id: str
    summary: str
    citations: list[CitationData]
    unknowns: list[str]
    model_invoked: bool
    endpoint_id: str | None
    model_id: str | None
    response_schema_version: str
    data_profile: str
    generated_at: datetime

    @classmethod
    def from_domain(cls, answer: GroundedAnswer) -> GroundedAnswerData:
        return cls.model_validate(answer, from_attributes=True)


class GroundedAnswerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: GroundedAnswerData
    meta: ResponseMeta
