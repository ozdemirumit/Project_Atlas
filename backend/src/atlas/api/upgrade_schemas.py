from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.upgrade.domain.upgrade import UpgradeReadinessPlan, UpgradeSimulation

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class UpgradeReadinessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(default="atlas.upgrade-readiness-request.v1", pattern=STABLE_ID)
    source_run_id: str = Field(pattern=STABLE_ID)
    backup_id: str = Field(pattern=STABLE_ID)
    restore_validation_id: str = Field(pattern=STABLE_ID)
    target_release_id: str = Field(pattern=STABLE_ID)


class MigrationStepData(BaseModel):
    step_id: str
    sequence: int
    migration_kind: str
    reversible: bool
    requires_quiescence: bool
    estimated_minutes: int


class ReadinessCheckData(BaseModel):
    check_id: str
    category_id: str
    result_code: str
    mandatory: bool
    passed: bool


class UpgradeReadinessData(BaseModel):
    plan_id: str
    schema_version: str
    catalog_version: str
    source_run_id: str
    source_run_version: int
    source_release_id: str
    source_release_version: str
    target_release_id: str
    target_release_version: str
    profile: str
    source_configuration_digest: str
    source_schema_version: str
    target_schema_version: str
    target_manifest_digest: str
    backup_id: str
    backup_archive_sha256: str
    restore_validation_id: str
    restore_validation_digest: str
    source_evidence_digest: str
    migration_steps: list[MigrationStepData]
    service_dependency_ids: list[str]
    abort_criterion_ids: list[str]
    rollback_step_ids: list[str]
    post_verification_check_ids: list[str]
    readiness_checks: list[ReadinessCheckData]
    estimated_downtime_min_minutes: int
    estimated_downtime_max_minutes: int
    rollback_window_minutes: int
    rollback_supported: bool
    forward_recovery_required_after_step_id: str | None
    state: str
    plan_digest: str
    generated_at: datetime
    expires_at: datetime
    production_authorized: bool
    execution_authorized: bool
    active_state_mutation_performed: bool

    @classmethod
    def from_domain(cls, item: UpgradeReadinessPlan) -> UpgradeReadinessData:
        return cls(
            **{
                field: getattr(item, field)
                for field in cls.model_fields
                if field
                not in {
                    "migration_steps",
                    "service_dependency_ids",
                    "abort_criterion_ids",
                    "rollback_step_ids",
                    "post_verification_check_ids",
                    "readiness_checks",
                    "state",
                }
            },
            state=item.state.value,
            migration_steps=[
                MigrationStepData(
                    step_id=step.step_id,
                    sequence=step.sequence,
                    migration_kind=step.migration_kind,
                    reversible=step.reversible,
                    requires_quiescence=step.requires_quiescence,
                    estimated_minutes=step.estimated_minutes,
                )
                for step in item.migration_steps
            ],
            service_dependency_ids=list(item.service_dependency_ids),
            abort_criterion_ids=list(item.abort_criterion_ids),
            rollback_step_ids=list(item.rollback_step_ids),
            post_verification_check_ids=list(item.post_verification_check_ids),
            readiness_checks=[
                ReadinessCheckData(
                    check_id=check.check_id,
                    category_id=check.category_id,
                    result_code=check.result_code,
                    mandatory=check.mandatory,
                    passed=check.passed,
                )
                for check in item.readiness_checks
            ],
        )


class UpgradeReadinessResponse(BaseModel):
    data: UpgradeReadinessData
    meta: ResponseMeta


class UpgradeSimulationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(default="atlas.upgrade-simulation-request.v1", pattern=STABLE_ID)
    source_run_version: int = Field(ge=1)
    backup_id: str = Field(pattern=STABLE_ID)
    restore_validation_id: str = Field(pattern=STABLE_ID)
    target_release_id: str = Field(pattern=STABLE_ID)
    plan_id: str = Field(pattern=STABLE_ID)
    plan_digest: str = Field(pattern=DIGEST)
    source_evidence_digest: str = Field(pattern=DIGEST)
    justification: str = Field(min_length=12, max_length=500)
    confirmed_isolated: bool


class SimulationStepData(BaseModel):
    step_id: str
    sequence: int
    state: str
    result_code: str
    rollback_applicable: bool
    simulated_minutes: int


class UpgradeSimulationData(BaseModel):
    simulation_id: str
    schema_version: str
    state: str
    source_run_id: str
    source_run_version: int
    plan_id: str
    plan_digest: str
    backup_id: str
    restore_validation_id: str
    steps: list[SimulationStepData]
    impacted_service_ids: list[str]
    post_verification_check_ids: list[str]
    abort_injected_at_step_id: str
    rollback_decision: str
    estimated_downtime_minutes: int
    simulation_digest: str
    created_at: datetime
    isolated_target: bool
    reused: bool
    production_authorized: bool
    artifact_acquisition_performed: bool
    database_migration_performed: bool
    service_restart_performed: bool
    traffic_switch_performed: bool
    active_restore_performed: bool
    secret_resolution_performed: bool
    network_request_performed: bool
    model_inference_performed: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(cls, item: UpgradeSimulation) -> UpgradeSimulationData:
        return cls(
            **{
                field: getattr(item, field)
                for field in cls.model_fields
                if field
                not in {"state", "steps", "impacted_service_ids", "post_verification_check_ids"}
            },
            state=item.state.value,
            steps=[
                SimulationStepData(
                    step_id=step.step_id,
                    sequence=step.sequence,
                    state=step.state.value,
                    result_code=step.result_code,
                    rollback_applicable=step.rollback_applicable,
                    simulated_minutes=step.simulated_minutes,
                )
                for step in item.steps
            ],
            impacted_service_ids=list(item.impacted_service_ids),
            post_verification_check_ids=list(item.post_verification_check_ids),
        )


class UpgradeSimulationResponse(BaseModel):
    data: UpgradeSimulationData
    meta: ResponseMeta
