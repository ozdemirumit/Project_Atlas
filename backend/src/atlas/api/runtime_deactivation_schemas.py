from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.runtime_deactivation import (
    ConnectorRuntimeDeactivationRecord,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorRuntimeDeactivationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-runtime-deactivation-input.v1", pattern=STABLE_ID
    )
    expected_activation_version: int | None = Field(default=None, ge=1)
    expected_activation_digest: str | None = Field(default=None, pattern=DIGEST)
    reason: str = Field(min_length=20, max_length=1000)
    acknowledged_runtime_only_deactivation: bool

    @model_validator(mode="after")
    def require_activation_precondition(self) -> ConnectorRuntimeDeactivationInput:
        if self.expected_activation_version is None and self.expected_activation_digest is None:
            raise ValueError("An activation version or immutable digest is required")
        return self


class ConnectorRuntimeDeactivationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deactivation_id: str
    activation_id: str
    activation_version: int
    connector_id: str
    instance_id: str
    effective_runtime_state: Literal["disabled_runtime"]
    deactivated_by: str
    reason: str
    deactivated_at: datetime
    atlas_runtime_disabled: Literal[True]
    target_authority_revoked: Literal[True]
    managed_infrastructure_contacted: Literal[False]
    infrastructure_mutation_performed: Literal[False]
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorRuntimeDeactivationRecord
    ) -> ConnectorRuntimeDeactivationData:
        return cls.model_validate({field: getattr(record, field) for field in cls.model_fields})


class ConnectorRuntimeDeactivationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorRuntimeDeactivationData
    meta: ResponseMeta


class ConnectorRuntimeDeactivationInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorRuntimeDeactivationData, ...]
    meta: ResponseMeta
