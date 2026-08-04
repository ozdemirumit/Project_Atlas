from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.bootstrap_state_schemas import ArtifactAcquisitionData, BootstrapRunData
from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import (
    ArtifactAcquisitionState,
    ArtifactDisposition,
)
from atlas.modules.platform.domain.bootstrap_state import BootstrapMutationResult
from atlas.modules.platform.domain.release_preflight import (
    AcquisitionMode,
    DeploymentProfile,
    PreflightState,
)

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class BootstrapArtifactAcquisitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-artifact-acquisition.v1"]
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_version: int = Field(ge=1)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    phase_id: Literal["phase.acquire"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    manifest_digest: str = Field(pattern=DIGEST_PATTERN)
    mode: AcquisitionMode
    profile: DeploymentProfile
    preflight_report_id: str = Field(pattern=STABLE_ID_PATTERN)
    preflight_state: PreflightState
    warning_accepted: bool = False
    justification: str = Field(min_length=12, max_length=500)

    @field_validator("preflight_state")
    @classmethod
    def validate_preflight_state(cls, value: PreflightState) -> PreflightState:
        if value is PreflightState.UNCHECKED:
            raise ValueError("unchecked preflight cannot authorize artifact acquisition")
        return value

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("justification must be trimmed single-line text")
        return value


class BootstrapArtifactAcquisitionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData
    execution: ArtifactAcquisitionData
    replayed: bool
    artifact_storage_mutation_performed: bool
    configuration_mutation_authorized: bool = False
    service_deployment_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
    ai_operation_authorized: bool = False

    @classmethod
    def from_domain(cls, result: BootstrapMutationResult) -> BootstrapArtifactAcquisitionData:
        execution = result.artifact_acquisition
        if execution is None:
            raise ValueError("artifact acquisition response requires execution evidence")
        mutated = execution.state is ArtifactAcquisitionState.COMPLETED and any(
            item.disposition is ArtifactDisposition.PUBLISHED for item in execution.evidence
        )
        return cls(
            run=BootstrapRunData.from_domain(result.record),
            execution=ArtifactAcquisitionData.from_domain(execution),
            replayed=result.replayed,
            artifact_storage_mutation_performed=mutated,
        )


class BootstrapArtifactAcquisitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapArtifactAcquisitionData
    meta: ResponseMeta
