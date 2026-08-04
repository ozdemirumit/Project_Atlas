from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.bootstrap_state_schemas import BootstrapRunData, IntegrationValidationData
from atlas.api.deployment_configuration_schemas import DeploymentConfigurationOverlayInput
from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_integration_validation import (
    BootstrapIntegrationPlan,
    IntegrationStateDisposition,
    IntegrationTargetState,
    IntegrationValidationState,
)
from atlas.modules.platform.domain.bootstrap_state import BootstrapMutationResult
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class BootstrapIntegrationPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-integration-plan-request.v1"]
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
    service_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    identity_plan_digest: str = Field(pattern=DIGEST_PATTERN)


class ModelEndpointRegistrationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_id: str
    owner_id: str
    provider_type: str
    service_reference_id: str
    credential_reference_id: str
    model_id: str
    context_limit: int
    output_limit: int
    data_classification_ceiling: str
    residency_boundary_id: str
    timeout_seconds: int
    max_retries: int
    rate_limit_per_minute: int
    concurrency_limit: int
    telemetry_classification: str
    approved_task_class_ids: list[str]


class CoreIntegrationRegistrationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    integration_id: str
    integration_type: str
    owner_id: str
    purpose_id: str
    classification: str
    endpoint_reference_id: str
    trust_reference_id: str
    credential_reference_id: str | None
    scope_id: str
    rate_limit_per_minute: int
    validation_operation_id: str
    mapping_preview_id: str
    data_flow_id: str
    activation_state: str


class IntegrationPlanCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    subject_id: str
    state: str
    result_code: str
    mandatory: bool


class BootstrapIntegrationPlanData(BaseModel):
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
    service_plan_digest: str
    identity_plan_digest: str
    integration_plan_digest: str
    target_id: str
    target_kind: str
    target_state: str
    model_endpoint: ModelEndpointRegistrationData
    integrations: list[CoreIntegrationRegistrationData]
    checks: list[IntegrationPlanCheckData]
    state: str
    result_code: str
    generated_at: datetime
    actual_model_request_authorized: bool = False
    network_request_authorized: bool = False
    secret_resolution_authorized: bool = False
    integration_activation_authorized: bool = False
    connector_invocation_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    @classmethod
    def from_domain(cls, plan: BootstrapIntegrationPlan) -> BootstrapIntegrationPlanData:
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
            service_plan_digest=plan.service_plan_digest,
            identity_plan_digest=plan.identity_plan_digest,
            integration_plan_digest=plan.integration_plan_digest,
            target_id=plan.target_id,
            target_kind=plan.target_kind,
            target_state=plan.target_state.value,
            model_endpoint=ModelEndpointRegistrationData(
                endpoint_id=plan.model_endpoint.endpoint_id,
                owner_id=plan.model_endpoint.owner_id,
                provider_type=plan.model_endpoint.provider_type,
                service_reference_id=plan.model_endpoint.service_reference_id,
                credential_reference_id=plan.model_endpoint.credential_reference_id,
                model_id=plan.model_endpoint.model_id,
                context_limit=plan.model_endpoint.context_limit,
                output_limit=plan.model_endpoint.output_limit,
                data_classification_ceiling=plan.model_endpoint.data_classification_ceiling,
                residency_boundary_id=plan.model_endpoint.residency_boundary_id,
                timeout_seconds=plan.model_endpoint.timeout_seconds,
                max_retries=plan.model_endpoint.max_retries,
                rate_limit_per_minute=plan.model_endpoint.rate_limit_per_minute,
                concurrency_limit=plan.model_endpoint.concurrency_limit,
                telemetry_classification=plan.model_endpoint.telemetry_classification,
                approved_task_class_ids=list(plan.model_endpoint.approved_task_class_ids),
            ),
            integrations=[
                CoreIntegrationRegistrationData(
                    integration_id=item.integration_id,
                    integration_type=item.integration_type,
                    owner_id=item.owner_id,
                    purpose_id=item.purpose_id,
                    classification=item.classification,
                    endpoint_reference_id=item.endpoint_reference_id,
                    trust_reference_id=item.trust_reference_id,
                    credential_reference_id=item.credential_reference_id,
                    scope_id=item.scope_id,
                    rate_limit_per_minute=item.rate_limit_per_minute,
                    validation_operation_id=item.validation_operation_id,
                    mapping_preview_id=item.mapping_preview_id,
                    data_flow_id=item.data_flow_id,
                    activation_state=item.activation_state.value,
                )
                for item in plan.integrations
            ],
            checks=[
                IntegrationPlanCheckData(
                    check_id=item.check_id,
                    subject_id=item.subject_id,
                    state=item.state.value,
                    result_code=item.result_code,
                    mandatory=item.mandatory,
                )
                for item in plan.checks
            ],
            state=plan.state.value,
            result_code=plan.result_code,
            generated_at=plan.generated_at,
        )


class BootstrapIntegrationPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapIntegrationPlanData
    meta: ResponseMeta


class BootstrapIntegrationValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-integration-validation.v1"]
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_version: int = Field(ge=1)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    phase_id: Literal["phase.integrations"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    overlay: DeploymentConfigurationOverlayInput
    trust_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    data_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    migration_artifact_digest: str = Field(pattern=DIGEST_PATTERN)
    service_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    identity_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    integration_schema_version: Literal["atlas.bootstrap-integration-plan.v1"]
    integration_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    target_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_target_state: IntegrationTargetState
    justification: str = Field(min_length=12, max_length=500)

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("justification must be trimmed single-line text")
        return value


class BootstrapIntegrationValidationResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData
    execution: IntegrationValidationData
    replayed: bool
    synthetic_state_mutation_performed: bool
    actual_model_request_performed: bool = False
    network_request_performed: bool = False
    secret_resolution_performed: bool = False
    integration_activation_performed: bool = False
    connector_invocation_performed: bool = False
    knowledge_ingestion_performed: bool = False
    infrastructure_mutation_performed: bool = False
    ai_advice_generated: bool = False

    @classmethod
    def from_domain(
        cls, result: BootstrapMutationResult
    ) -> BootstrapIntegrationValidationResultData:
        execution = result.integration_validation
        if execution is None:
            raise ValueError("integration response requires execution evidence")
        mutated = execution.state is IntegrationValidationState.COMPLETED and any(
            item.disposition is IntegrationStateDisposition.PUBLISHED for item in execution.evidence
        )
        return cls(
            run=BootstrapRunData.from_domain(result.record),
            execution=IntegrationValidationData.from_domain(execution),
            replayed=result.replayed,
            synthetic_state_mutation_performed=mutated,
        )


class BootstrapIntegrationValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapIntegrationValidationResultData
    meta: ResponseMeta
