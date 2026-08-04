from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.bootstrap_state_schemas import BootstrapRunData, EndToEndVerificationData
from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_end_to_end_verification import (
    BootstrapVerificationPlan,
    VerificationExecutionState,
    VerificationReportDisposition,
    VerificationTargetState,
)
from atlas.modules.platform.domain.bootstrap_state import BootstrapMutationResult
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class BootstrapVerificationPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-verification-plan-request.v1"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    source_run_id: str = Field(pattern=STABLE_ID_PATTERN)
    source_run_version: int = Field(ge=1)
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    trust_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    data_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    service_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    identity_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    integration_plan_digest: str = Field(pattern=DIGEST_PATTERN)


class VerificationPlanCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    category_id: str
    subject_id: str
    state: str
    result_code: str
    mandatory: bool


class BootstrapVerificationPlanData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    suite_version: str
    release_id: str
    profile: str
    organization_id: str
    environment_id: str
    site_id: str
    source_run_id: str
    source_run_version: int
    configuration_digest: str
    trust_plan_digest: str
    data_plan_digest: str
    service_plan_digest: str
    identity_plan_digest: str
    integration_plan_digest: str
    verification_plan_digest: str
    ingress_contract_id: str
    target_id: str
    target_kind: str
    target_state: str
    checks: list[VerificationPlanCheckData]
    state: str
    result_code: str
    generated_at: datetime
    external_operations_authorized: bool = False

    @classmethod
    def from_domain(cls, plan: BootstrapVerificationPlan) -> BootstrapVerificationPlanData:
        return cls(
            schema_version=plan.schema_version,
            suite_version=plan.suite_version,
            release_id=plan.release_id,
            profile=plan.profile.value,
            organization_id=plan.organization_id,
            environment_id=plan.environment_id,
            site_id=plan.site_id,
            source_run_id=plan.source_run_id,
            source_run_version=plan.source_run_version,
            configuration_digest=plan.configuration_digest,
            trust_plan_digest=plan.trust_plan_digest,
            data_plan_digest=plan.data_plan_digest,
            service_plan_digest=plan.service_plan_digest,
            identity_plan_digest=plan.identity_plan_digest,
            integration_plan_digest=plan.integration_plan_digest,
            verification_plan_digest=plan.verification_plan_digest,
            ingress_contract_id=plan.ingress_contract_id,
            target_id=plan.target_id,
            target_kind=plan.target_kind,
            target_state=plan.target_state.value,
            checks=[
                VerificationPlanCheckData(
                    check_id=item.check_id,
                    category_id=item.category_id,
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


class BootstrapVerificationPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapVerificationPlanData
    meta: ResponseMeta


class BootstrapVerificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-verification.v1"]
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_version: int = Field(ge=1)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    phase_id: Literal["phase.verify"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    trust_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    data_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    service_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    identity_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    integration_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    verification_schema_version: Literal["atlas.bootstrap-verification-plan.v1"]
    suite_version: Literal["atlas.bootstrap-verification-suite.v1"]
    verification_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    target_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_target_state: VerificationTargetState
    justification: str = Field(min_length=12, max_length=500)

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("justification must be trimmed single-line text")
        return value


class BootstrapVerificationResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData
    execution: EndToEndVerificationData
    replayed: bool
    synthetic_report_mutation_performed: bool
    model_request_performed: bool = False
    network_request_performed: bool = False
    secret_resolution_performed: bool = False
    connector_invocation_performed: bool = False
    knowledge_mutation_performed: bool = False
    workflow_execution_performed: bool = False
    approval_creation_performed: bool = False
    backup_restore_operation_performed: bool = False
    external_export_performed: bool = False
    infrastructure_mutation_performed: bool = False
    deployment_action_performed: bool = False
    ai_advice_generated: bool = False

    @classmethod
    def from_domain(cls, result: BootstrapMutationResult) -> BootstrapVerificationResultData:
        execution = result.end_to_end_verification
        if execution is None:
            raise ValueError("verification response requires execution evidence")
        mutated = execution.state is VerificationExecutionState.COMPLETED and any(
            item.disposition is VerificationReportDisposition.PUBLISHED
            for item in execution.evidence
        )
        return cls(
            run=BootstrapRunData.from_domain(result.record),
            execution=EndToEndVerificationData.from_domain(execution),
            replayed=result.replayed,
            synthetic_report_mutation_performed=mutated,
        )


class BootstrapVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapVerificationResultData
    meta: ResponseMeta
