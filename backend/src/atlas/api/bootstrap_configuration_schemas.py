from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.bootstrap_state_schemas import BootstrapRunData, ConfigurationRenderingData
from atlas.api.deployment_configuration_schemas import DeploymentConfigurationOverlayInput
from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationFileDisposition,
    ConfigurationRenderingState,
)
from atlas.modules.platform.domain.bootstrap_state import BootstrapMutationResult
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class BootstrapConfigurationRenderingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-configuration-rendering.v1"]
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_version: int = Field(ge=1)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    phase_id: Literal["phase.configure"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    configuration_schema_version: Literal["atlas.deployment-configuration.v1"]
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    overlay: DeploymentConfigurationOverlayInput
    justification: str = Field(min_length=12, max_length=500)

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("justification must be trimmed single-line text")
        return value


class BootstrapConfigurationRenderingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData
    execution: ConfigurationRenderingData
    replayed: bool
    configuration_storage_mutation_performed: bool
    trust_mutation_authorized: bool = False
    secret_mutation_authorized: bool = False
    data_mutation_authorized: bool = False
    service_deployment_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
    ai_operation_authorized: bool = False

    @classmethod
    def from_domain(cls, result: BootstrapMutationResult) -> BootstrapConfigurationRenderingData:
        execution = result.configuration_rendering
        if execution is None:
            raise ValueError("configuration rendering response requires execution evidence")
        mutated = execution.state is ConfigurationRenderingState.COMPLETED and any(
            item.disposition is ConfigurationFileDisposition.PUBLISHED
            for item in execution.evidence
        )
        return cls(
            run=BootstrapRunData.from_domain(result.record),
            execution=ConfigurationRenderingData.from_domain(execution),
            replayed=result.replayed,
            configuration_storage_mutation_performed=mutated,
        )


class BootstrapConfigurationRenderingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapConfigurationRenderingData
    meta: ResponseMeta
