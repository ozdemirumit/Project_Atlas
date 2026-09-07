from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta


class FeedbackSubmitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=256)
    item_version: str = Field(min_length=1, max_length=64)
    kind: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=4096)


class FeedbackResolvePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution_notes: str = Field(min_length=1, max_length=4096)
    dismissed: bool = False


class FeedbackData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: str
    item_id: str
    item_version: str
    kind: str
    submitted_by: str
    submitted_at: datetime
    description: str
    state: str
    triaged_by: str | None = None
    triaged_at: datetime | None = None
    resolution_notes: str | None = None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: FeedbackData
    meta: ResponseMeta
