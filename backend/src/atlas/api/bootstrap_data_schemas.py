from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.bootstrap_state_schemas import BootstrapRunData, DataInitializationData
from atlas.api.deployment_configuration_schemas import DeploymentConfigurationOverlayInput
from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_data_initialization import (
    BootstrapDataPlan,
    DataInitializationState,
    DataStateDisposition,
    DataTargetState,
)
from atlas.modules.platform.domain.bootstrap_state import BootstrapMutationResult
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class BootstrapDataPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-data-plan-request.v1"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    overlay: DeploymentConfigurationOverlayInput
    trust_plan_digest: str = Field(pattern=DIGEST_PATTERN)


class BootstrapMigrationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    migration_id: str
    sequence: int
    sha256: str
    from_revision: str
    to_revision: str
    compatibility: str
    reversible: bool
    destructive: bool
    recovery_code: str
    expected_object_count: int


class BootstrapDataPlanData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    release_id: str
    profile: str
    organization_id: str
    environment_id: str
    site_id: str
    configuration_digest: str
    trust_plan_digest: str
    migration_artifact_digest: str
    data_plan_digest: str
    target_id: str
    target_kind: str
    current_revision: str
    target_revision: str
    target_state: str
    state: str
    result_code: str
    migrations: list[BootstrapMigrationData]
    backup_applicability: str
    generated_at: datetime
    database_url_present: bool = False
    credential_material_present: bool = False
    sql_text_present: bool = False
    destructive_migration_authorized: bool = False
    backup_operation_authorized: bool = False
    service_deployment_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
    ai_operation_authorized: bool = False

    @classmethod
    def from_domain(cls, plan: BootstrapDataPlan) -> BootstrapDataPlanData:
        return cls(
            schema_version=plan.schema_version,
            release_id=plan.release_id,
            profile=plan.profile.value,
            organization_id=plan.organization_id,
            environment_id=plan.environment_id,
            site_id=plan.site_id,
            configuration_digest=plan.configuration_digest,
            trust_plan_digest=plan.trust_plan_digest,
            migration_artifact_digest=plan.migration_artifact_digest,
            data_plan_digest=plan.data_plan_digest,
            target_id=plan.target_id,
            target_kind=plan.target_kind,
            current_revision=plan.current_revision,
            target_revision=plan.target_revision,
            target_state=plan.target_state.value,
            state=plan.state.value,
            result_code=plan.result_code,
            migrations=[
                BootstrapMigrationData(
                    migration_id=item.migration_id,
                    sequence=item.sequence,
                    sha256=item.sha256,
                    from_revision=item.from_revision,
                    to_revision=item.to_revision,
                    compatibility=item.compatibility.value,
                    reversible=item.reversible,
                    destructive=item.destructive,
                    recovery_code=item.recovery_code,
                    expected_object_count=item.expected_object_count,
                )
                for item in plan.migrations
            ],
            backup_applicability=plan.backup_applicability.value,
            generated_at=plan.generated_at,
        )


class BootstrapDataPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapDataPlanData
    meta: ResponseMeta


class BootstrapDataInitializationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-data-initialization.v1"]
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_version: int = Field(ge=1)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    phase_id: Literal["phase.data"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    overlay: DeploymentConfigurationOverlayInput
    trust_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    data_schema_version: Literal["atlas.bootstrap-data-plan.v1"]
    data_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    migration_artifact_digest: str = Field(pattern=DIGEST_PATTERN)
    target_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_target_state: DataTargetState
    justification: str = Field(min_length=12, max_length=500)

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("justification must be trimmed single-line text")
        return value


class BootstrapDataInitializationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData
    execution: DataInitializationData
    replayed: bool
    schema_state_mutation_performed: bool
    external_database_provisioning_performed: bool = False
    destructive_migration_performed: bool = False
    backup_operation_performed: bool = False
    service_deployment_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
    ai_operation_authorized: bool = False

    @classmethod
    def from_domain(cls, result: BootstrapMutationResult) -> BootstrapDataInitializationData:
        execution = result.data_initialization
        if execution is None:
            raise ValueError("data initialization response requires execution evidence")
        mutated = execution.state is DataInitializationState.COMPLETED and any(
            item.disposition is DataStateDisposition.PUBLISHED for item in execution.evidence
        )
        return cls(
            run=BootstrapRunData.from_domain(result.record),
            execution=DataInitializationData.from_domain(execution),
            replayed=result.replayed,
            schema_state_mutation_performed=mutated,
        )


class BootstrapDataInitializationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapDataInitializationData
    meta: ResponseMeta
