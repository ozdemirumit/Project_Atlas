from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta


class LegalHoldPlacePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hold_id: str = Field(min_length=1, max_length=256)
    item_id: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=4096)


class DeletionRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=256)
    item_id: str = Field(min_length=1, max_length=256)
    retention_policy_reference: str = Field(min_length=1, max_length=1024)


class DeletionCompletePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tombstone_id: str = Field(min_length=1, max_length=256)
    reason_code: str = Field(min_length=1, max_length=128)


class LegalHoldData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hold_id: str
    item_id: str
    authorized_by: str
    reason: str
    placed_at: datetime
    released_at: datetime | None = None
    release_authorized_by: str | None = None


class LegalHoldResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: LegalHoldData
    meta: ResponseMeta


class DeletionRequestData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    item_id: str
    requested_by: str
    requested_at: datetime
    retention_policy_reference: str
    state: str
    completed_at: datetime | None = None
    derived_artifacts_removed: bool = False
    tombstone_id: str | None = None


class DeletionRequestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DeletionRequestData
    meta: ResponseMeta
