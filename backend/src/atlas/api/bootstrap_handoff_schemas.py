from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.bootstrap_state_schemas import BootstrapRunData, OperationalHandoffData
from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_operational_handoff import (
    BootstrapHandoffPlan,
    HandoffExecutionState,
    HandoffReadinessClaims,
    HandoffReportDisposition,
    HandoffTargetState,
)
from atlas.modules.platform.domain.bootstrap_state import BootstrapMutationResult
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class BootstrapHandoffPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-handoff-plan-request.v1"]
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
    verification_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    verification_report_digest: str = Field(pattern=DIGEST_PATTERN)


class HandoffPlanCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    category_id: str
    subject_id: str
    state: str
    result_code: str
    mandatory: bool


class BootstrapHandoffPlanData(BaseModel):
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
    verification_report_digest: str
    source_evidence_digest: str
    handoff_plan_digest: str
    ingress_contract_id: str
    target_id: str
    target_kind: str
    target_state: str
    readiness_class: str
    readiness_claims: dict[str, bool]
    known_limitation_ids: list[str]
    pending_action_ids: list[str]
    owner_role_ids: list[str]
    missing_production_evidence_ids: list[str]
    checks: list[HandoffPlanCheckData]
    state: str
    result_code: str
    generated_at: datetime
    external_operations_authorized: bool = False

    @classmethod
    def from_domain(cls, plan: BootstrapHandoffPlan) -> BootstrapHandoffPlanData:
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
            verification_report_digest=plan.verification_report_digest,
            source_evidence_digest=plan.source_evidence_digest,
            handoff_plan_digest=plan.handoff_plan_digest,
            ingress_contract_id=plan.ingress_contract_id,
            target_id=plan.target_id,
            target_kind=plan.target_kind,
            target_state=plan.target_state.value,
            readiness_class=plan.readiness_class.value,
            readiness_claims=cls._claims(plan.readiness_claims),
            known_limitation_ids=list(plan.known_limitation_ids),
            pending_action_ids=list(plan.pending_action_ids),
            owner_role_ids=list(plan.owner_role_ids),
            missing_production_evidence_ids=list(plan.missing_production_evidence_ids),
            checks=[
                HandoffPlanCheckData(
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

    @staticmethod
    def _claims(claims: HandoffReadinessClaims) -> dict[str, bool]:
        return {
            "production_ready": claims.production_ready,
            "customer_integrations_validated": claims.customer_integrations_validated,
            "support_accepted": claims.support_accepted,
            "ha_certified": claims.ha_certified,
            "dr_certified": claims.dr_certified,
            "backup_restore_validated": claims.backup_restore_validated,
            "release_approved": claims.release_approved,
        }


class BootstrapHandoffPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapHandoffPlanData
    meta: ResponseMeta


class BootstrapHandoffInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-handoff.v1"]
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_version: int = Field(ge=1)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    phase_id: Literal["phase.handoff"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    trust_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    data_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    service_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    identity_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    integration_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    verification_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    verification_report_digest: str = Field(pattern=DIGEST_PATTERN)
    source_evidence_digest: str = Field(pattern=DIGEST_PATTERN)
    handoff_schema_version: Literal["atlas.bootstrap-handoff-plan.v1"]
    suite_version: Literal["atlas.bootstrap-handoff-suite.v1"]
    handoff_plan_digest: str = Field(pattern=DIGEST_PATTERN)
    target_id: str = Field(pattern=STABLE_ID_PATTERN)
    expected_target_state: HandoffTargetState
    justification: str = Field(min_length=12, max_length=500)

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("justification must be trimmed single-line text")
        return value


class BootstrapHandoffResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData
    execution: OperationalHandoffData
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
    support_bundle_export_performed: bool = False
    ticket_creation_performed: bool = False
    notification_performed: bool = False
    infrastructure_mutation_performed: bool = False
    deployment_action_performed: bool = False
    ai_advice_generated: bool = False

    @classmethod
    def from_domain(cls, result: BootstrapMutationResult) -> BootstrapHandoffResultData:
        execution = result.operational_handoff
        if execution is None:
            raise ValueError("handoff response requires execution evidence")
        mutated = execution.state is HandoffExecutionState.COMPLETED and any(
            item.disposition is HandoffReportDisposition.PUBLISHED for item in execution.evidence
        )
        return cls(
            run=BootstrapRunData.from_domain(result.record),
            execution=OperationalHandoffData.from_domain(execution),
            replayed=result.replayed,
            synthetic_report_mutation_performed=mutated,
        )


class BootstrapHandoffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapHandoffResultData
    meta: ResponseMeta
