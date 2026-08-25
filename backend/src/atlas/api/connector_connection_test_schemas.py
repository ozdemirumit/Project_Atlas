from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)
from atlas.modules.connectors.domain.bundled_runtime_state import (
    BundledConnectorRuntimeState,
)
from atlas.modules.connectors.domain.connection_test import ConnectorConnectionTestResult

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"


class BundledConnectionConfigurationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str = Field(min_length=1, max_length=253)
    port: int = Field(ge=1, le=65_535)
    trust_profile_id: str = Field(pattern=STABLE_ID)
    secret_reference_id: str = Field(pattern=STABLE_ID)
    secret: SecretStr | None = Field(default=None, exclude=True, repr=False)


class BundledConnectionConfigurationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configuration_id: str
    connector_id: str
    instance_id: str
    hostname: str
    port: int
    trust_profile_id: str
    secret_reference_id: str
    configured_at: datetime
    protocol: Literal["https"]
    development_only: Literal[True]
    secret_material_stored: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, record: BundledConnectionConfiguration
    ) -> BundledConnectionConfigurationData:
        return cls.model_validate({field: getattr(record, field) for field in cls.model_fields})


class BundledConnectionConfigurationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BundledConnectionConfigurationData
    meta: ResponseMeta


class ConnectorConnectionTestData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_id: str
    connector_id: str
    instance_id: str
    outcome: Literal["passed", "failed"]
    result_code: str
    retryable: bool
    checked_at: datetime
    duration_ms: int
    read_only_request_performed: bool
    target_details_disclosed: Literal[False]
    secret_material_disclosed: Literal[False]
    managed_infrastructure_contacted: bool
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(cls, result: ConnectorConnectionTestResult) -> ConnectorConnectionTestData:
        return cls.model_validate({field: getattr(result, field) for field in cls.model_fields})


class ConnectorConnectionTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorConnectionTestData
    meta: ResponseMeta


class BundledRuntimeEnableInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledged_read_only_operation: Literal[True]


class BundledRuntimeDisableInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=20, max_length=1000)
    acknowledged_runtime_stop: Literal[True]


class BundledRuntimeStateData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_id: str
    state: Literal["disabled", "enabled_read_only"]
    version: int
    changed_at: datetime | None
    changed_by: str | None
    reason: str | None
    managed_infrastructure_contacted: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(cls, record: BundledConnectorRuntimeState) -> BundledRuntimeStateData:
        return cls.model_validate({field: getattr(record, field) for field in cls.model_fields})


class BundledRuntimeStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BundledRuntimeStateData
    meta: ResponseMeta
