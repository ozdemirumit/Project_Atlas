from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta


class RegisterItsmCiMappingRulePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    external_ci_class: str = Field(min_length=1, max_length=128)
    atlas_entity_type: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=256)


class ItsmCiMappingRuleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    version: int
    external_ci_class: str
    atlas_entity_type: str
    profile_id: str


class ItsmCiMappingRuleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmCiMappingRuleData
    meta: ResponseMeta


class RecordItsmCiReconciliationConflictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_ci_id: str = Field(min_length=1, max_length=256)
    mapped_atlas_entity_id: str = Field(min_length=1, max_length=256)
    field: str = Field(min_length=1, max_length=32)
    cmdb_value: str = Field(min_length=1, max_length=1000)
    cmdb_observed_at: datetime
    live_value: str = Field(min_length=1, max_length=1000)
    live_observed_at: datetime
    proposed_authority: str = Field(min_length=1, max_length=32)
    confidence: float = Field(ge=0.0, le=1.0)


class UpdateItsmCiReconciliationMatchStatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_state: str = Field(min_length=1, max_length=32)


class ItsmCiReconciliationConflictData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    external_ci_id: str
    mapped_atlas_entity_id: str
    field: str
    cmdb_value: str
    cmdb_observed_at: str
    live_value: str
    live_observed_at: str
    proposed_authority: str
    confidence: float
    match_state: str


class ItsmCiReconciliationConflictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmCiReconciliationConflictData
    meta: ResponseMeta
