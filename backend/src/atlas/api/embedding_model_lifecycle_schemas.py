from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta


class EmbeddingModelTransitionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_stage: str = Field(min_length=1, max_length=32)


class EmbeddingModelLifecycleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str
    stage: str


class EmbeddingModelLifecycleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: EmbeddingModelLifecycleData
    meta: ResponseMeta
