from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.bootstrap_state_schemas import BootstrapRunData, ServiceDeploymentData
from atlas.api.deployment_configuration_schemas import DeploymentConfigurationOverlayInput
from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_service_deployment import (
    BootstrapServicePlan,
    ServiceDeploymentState,
    ServiceStateDisposition,
    ServiceTargetState,
)
from atlas.modules.platform.domain.bootstrap_state import BootstrapMutationResult
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class BootstrapServicePlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-service-plan-request.v1"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    overlay: DeploymentConfigurationOverlayInput
    trust_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    data_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    migration_artifact_digest: str = Field(pattern=DIGEST_PATTERN)


class BootstrapServiceSpecData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_id: str
    sequence: int
    artifact_id: str
    artifact_sha256: str
    dependencies: list[str]
    workload_identity_id: str | None
    endpoint_class: str
    cpu_limit_millicores: int
    memory_limit_mb: int
    startup_probe_id: str
    readiness_probe_id: str
    liveness_probe_id: str
    run_as_root: bool
    privileged: bool
    arbitrary_public_egress: bool


class BootstrapServicePlanData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    release_id: str
    profile: str
    organization_id: str
    environment_id: str
    site_id: str
    configuration_digest: str
    trust_plan_digest: str
    data_plan_digest: str
    migration_artifact_digest: str
    service_plan_digest: str
    target_id: str
    target_kind: str
    target_state: str
    state: str
    result_code: str
    services: list[BootstrapServiceSpecData]
    generated_at: datetime
    real_process_mutation_authorized: bool = False
    container_runtime_mutation_authorized: bool = False
    operating_system_service_mutation_authorized: bool = False
    network_mutation_authorized: bool = False
    secret_mutation_authorized: bool = False
    external_data_mutation_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
    ai_operation_authorized: bool = False

    @classmethod
    def from_domain(cls, plan: BootstrapServicePlan) -> BootstrapServicePlanData:
        return cls(
            schema_version=plan.schema_version,
            release_id=plan.release_id,
            profile=plan.profile.value,
            organization_id=plan.organization_id,
            environment_id=plan.environment_id,
            site_id=plan.site_id,
            configuration_digest=plan.configuration_digest,
            trust_plan_digest=plan.trust_plan_digest,
            data_plan_digest=plan.data_plan_digest,
            migration_artifact_digest=plan.migration_artifact_digest,
            service_plan_digest=plan.service_plan_digest,
            target_id=plan.target_id,
            target_kind=plan.target_kind,
            target_state=plan.target_state.value,
            state=plan.state.value,
            result_code=plan.result_code,
            services=[
                BootstrapServiceSpecData(
                    service_id=item.service_id,
                    sequence=item.sequence,
                    artifact_id=item.artifact_id,
                    artifact_sha256=item.artifact_sha256,
                    dependencies=list(item.dependencies),
                    workload_identity_id=item.workload_identity_id,
                    endpoint_class=item.endpoint_class.value,
                    cpu_limit_millicores=item.cpu_limit_millicores,
                    memory_limit_mb=item.memory_limit_mb,
                    startup_probe_id=item.startup_probe_id,
                    readiness_probe_id=item.readiness_probe_id,
                    liveness_probe_id=item.liveness_probe_id,
                    run_as_root=item.run_as_root,
                    privileged=item.privileged,
                    arbitrary_public_egress=item.arbitrary_public_egress,
                )
                for item in plan.services
            ],
            generated_at=plan.generated_at,
        )


class BootstrapServicePlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapServicePlanData
    meta: ResponseMeta


class BootstrapServiceDeploymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-service-deployment.v1"]
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_version: int = Field(ge=1)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    phase_id: Literal["phase.services"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    overlay: DeploymentConfigurationOverlayInput
    trust_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    data_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    migration_artifact_digest: str = Field(pattern=DIGEST_PATTERN)
    service_schema_version: Literal["atlas.bootstrap-service-plan.v1"]
    service_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    target_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_target_state: ServiceTargetState
    justification: str = Field(min_length=12, max_length=500)

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("justification must be trimmed single-line text")
        return value


class BootstrapServiceDeploymentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData
    execution: ServiceDeploymentData
    replayed: bool
    synthetic_state_mutation_performed: bool
    real_process_mutation_performed: bool = False
    container_runtime_mutation_performed: bool = False
    operating_system_service_mutation_performed: bool = False
    port_or_network_mutation_performed: bool = False
    secret_mutation_performed: bool = False
    external_data_mutation_performed: bool = False
    infrastructure_mutation_performed: bool = False
    ai_operation_performed: bool = False

    @classmethod
    def from_domain(cls, result: BootstrapMutationResult) -> BootstrapServiceDeploymentData:
        execution = result.service_deployment
        if execution is None:
            raise ValueError("service deployment response requires execution evidence")
        mutated = execution.state is ServiceDeploymentState.COMPLETED and any(
            item.disposition is ServiceStateDisposition.PUBLISHED for item in execution.evidence
        )
        return cls(
            run=BootstrapRunData.from_domain(result.record),
            execution=ServiceDeploymentData.from_domain(execution),
            replayed=result.replayed,
            synthetic_state_mutation_performed=mutated,
        )


class BootstrapServiceDeploymentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapServiceDeploymentData
    meta: ResponseMeta
