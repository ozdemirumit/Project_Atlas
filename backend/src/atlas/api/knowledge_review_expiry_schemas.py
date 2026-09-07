from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta


class ReviewSchedulePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_version: str = Field(min_length=1, max_length=64)
    owner: str = Field(min_length=1, max_length=256)
    review_interval_days: int = Field(ge=1, le=3650)


class ReviewRenewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_reference: str = Field(min_length=1, max_length=1024)


class OwnerAbsenceResolvePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: str = Field(min_length=1, max_length=32)
    new_owner: str | None = Field(default=None, max_length=256)
    rationale: str = Field(min_length=1, max_length=4096)


class ReviewDueData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    item_version: str
    owner: str
    review_interval_days: int
    last_reviewed_at: datetime
    next_review_due_at: datetime


class ReviewDueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ReviewDueData
    meta: ResponseMeta


class ReviewRenewalData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    item_version: str
    renewed_by: str
    renewed_at: datetime
    evidence_reference: str
    next_review_due_at: datetime


class ReviewRenewalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ReviewRenewalData
    meta: ResponseMeta


class OwnerAbsenceResolutionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    prior_owner: str
    resolution: str
    new_owner: str | None
    resolved_by: str
    resolved_at: datetime
    rationale: str


class OwnerAbsenceResolutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OwnerAbsenceResolutionData
    meta: ResponseMeta
