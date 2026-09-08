from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta


class RecordItsmCreationIntentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=8, max_length=128)
    profile_id: str = Field(min_length=1, max_length=256)
    operation: str = Field(min_length=1, max_length=64)
    deduplication_signature: str = Field(min_length=1, max_length=256)


class ResolveItsmCreationIntentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: str = Field(min_length=1, max_length=32)
    external_record_id: str | None = Field(default=None, max_length=256)


class ItsmCreationIntentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent_id: str
    idempotency_key: str
    profile_id: str
    operation: str
    deduplication_signature: str
    state: str
    created_at: str
    resolved_at: str | None
    external_record_id: str | None


class ItsmCreationIntentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmCreationIntentData
    meta: ResponseMeta


class RecordItsmConflictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1, max_length=256)
    external_record_id: str = Field(min_length=1, max_length=256)
    kind: str = Field(min_length=1, max_length=64)
    last_known_source_version: str = Field(min_length=1, max_length=256)
    observed_source_version: str = Field(min_length=1, max_length=256)
    field_ownership: str = Field(min_length=1, max_length=32)


class ResolveItsmConflictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution_summary: str = Field(min_length=1, max_length=2000)


class ItsmConflictData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    profile_id: str
    external_record_id: str
    kind: str
    last_known_source_version: str
    observed_source_version: str
    field_ownership: str
    detected_at: str
    resolution_summary: str | None
    resolved_by: str | None
    resolved_at: str | None


class ItsmConflictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmConflictData
    meta: ResponseMeta
