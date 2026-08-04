from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

STABLE_ID = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[a-z0-9.]+)?$")


class UpgradePlanState(StrEnum):
    READY = "ready"


class UpgradeSimulationState(StrEnum):
    PASSED = "passed"


class SimulationStepState(StrEnum):
    SIMULATED = "simulated"


@dataclass(frozen=True, slots=True)
class UpgradeReadinessCheck:
    check_id: str
    category_id: str
    result_code: str
    mandatory: bool
    passed: bool

    def __post_init__(self) -> None:
        if any(
            STABLE_ID.fullmatch(value) is None
            for value in (self.check_id, self.category_id, self.result_code)
        ):
            raise ValueError("upgrade readiness check identifier is invalid")
        if self.mandatory and not self.passed:
            raise ValueError("mandatory upgrade readiness check must pass")


@dataclass(frozen=True, slots=True)
class MigrationStep:
    step_id: str
    sequence: int
    migration_kind: str
    reversible: bool
    requires_quiescence: bool
    estimated_minutes: int

    def __post_init__(self) -> None:
        if STABLE_ID.fullmatch(self.step_id) is None or self.sequence < 1:
            raise ValueError("migration step identity is invalid")
        if self.migration_kind not in {"application", "schema_expand", "projection_rebuild"}:
            raise ValueError("migration kind is unsupported")
        if not 1 <= self.estimated_minutes <= 120:
            raise ValueError("migration duration is invalid")


@dataclass(frozen=True, slots=True)
class UpgradeReadinessPlan:
    plan_id: str
    schema_version: str
    catalog_version: str
    organization_id: str
    environment_id: str
    site_id: str
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
    migration_steps: tuple[MigrationStep, ...]
    service_dependency_ids: tuple[str, ...]
    abort_criterion_ids: tuple[str, ...]
    rollback_step_ids: tuple[str, ...]
    post_verification_check_ids: tuple[str, ...]
    readiness_checks: tuple[UpgradeReadinessCheck, ...]
    estimated_downtime_min_minutes: int
    estimated_downtime_max_minutes: int
    rollback_window_minutes: int
    rollback_supported: bool
    forward_recovery_required_after_step_id: str | None
    state: UpgradePlanState
    plan_digest: str
    generated_at: datetime
    expires_at: datetime
    production_authorized: bool = False
    execution_authorized: bool = False
    active_state_mutation_performed: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.plan_id,
            self.schema_version,
            self.catalog_version,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.source_run_id,
            self.source_release_id,
            self.target_release_id,
            self.backup_id,
            self.restore_validation_id,
            self.source_schema_version,
            self.target_schema_version,
        )
        if any(STABLE_ID.fullmatch(value) is None for value in identifiers):
            raise ValueError("upgrade readiness identifier is invalid")
        if not SEMVER.fullmatch(self.source_release_version) or not SEMVER.fullmatch(
            self.target_release_version
        ):
            raise ValueError("upgrade release version is invalid")
        digests = (
            self.source_configuration_digest,
            self.target_manifest_digest,
            self.backup_archive_sha256,
            self.restore_validation_digest,
            self.source_evidence_digest,
            self.plan_digest,
        )
        if any(SHA256.fullmatch(value) is None for value in digests):
            raise ValueError("upgrade readiness digest is invalid")
        if self.source_run_version < 1 or self.generated_at >= self.expires_at:
            raise ValueError("upgrade readiness source or expiry is invalid")
        sequences = tuple(item.sequence for item in self.migration_steps)
        if sequences != tuple(range(1, len(sequences) + 1)) or len(sequences) != 3:
            raise ValueError("upgrade migration order is invalid")
        for values, expected in (
            (self.service_dependency_ids, 2),
            (self.abort_criterion_ids, 4),
            (self.rollback_step_ids, 4),
            (self.post_verification_check_ids, 6),
            (self.readiness_checks, 12),
        ):
            if len(values) != expected or len(set(values)) != expected:
                raise ValueError("upgrade readiness catalog is incomplete")
        if not (
            1 <= self.estimated_downtime_min_minutes <= self.estimated_downtime_max_minutes <= 240
        ):
            raise ValueError("upgrade downtime estimate is invalid")
        if not 15 <= self.rollback_window_minutes <= 1440 or not self.rollback_supported:
            raise ValueError("upgrade rollback policy is invalid")
        if (
            self.forward_recovery_required_after_step_id is not None
            and self.forward_recovery_required_after_step_id
            not in {item.step_id for item in self.migration_steps}
        ):
            raise ValueError("upgrade forward recovery boundary is invalid")
        if self.state is not UpgradePlanState.READY or any(
            (
                self.production_authorized,
                self.execution_authorized,
                self.active_state_mutation_performed,
            )
        ):
            raise ValueError("upgrade readiness plan violates safety boundaries")


@dataclass(frozen=True, slots=True)
class SimulationStep:
    step_id: str
    sequence: int
    state: SimulationStepState
    result_code: str
    rollback_applicable: bool
    simulated_minutes: int

    def __post_init__(self) -> None:
        if any(STABLE_ID.fullmatch(value) is None for value in (self.step_id, self.result_code)):
            raise ValueError("simulation step identity is invalid")
        if self.sequence < 1 or not 0 <= self.simulated_minutes <= 120:
            raise ValueError("simulation step timing is invalid")


@dataclass(frozen=True, slots=True)
class UpgradeSimulation:
    simulation_id: str
    schema_version: str
    state: UpgradeSimulationState
    actor_id: str
    organization_id: str
    environment_id: str
    site_id: str
    source_run_id: str
    source_run_version: int
    plan_id: str
    plan_digest: str
    backup_id: str
    restore_validation_id: str
    request_fingerprint: str
    idempotency_key: str
    steps: tuple[SimulationStep, ...]
    impacted_service_ids: tuple[str, ...]
    post_verification_check_ids: tuple[str, ...]
    abort_injected_at_step_id: str
    rollback_decision: str
    estimated_downtime_minutes: int
    simulation_digest: str
    created_at: datetime
    isolated_target: bool = True
    reused: bool = False
    production_authorized: bool = False
    artifact_acquisition_performed: bool = False
    database_migration_performed: bool = False
    service_restart_performed: bool = False
    traffic_switch_performed: bool = False
    active_restore_performed: bool = False
    secret_resolution_performed: bool = False
    network_request_performed: bool = False
    model_inference_performed: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.simulation_id,
            self.schema_version,
            self.actor_id,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.source_run_id,
            self.plan_id,
            self.backup_id,
            self.restore_validation_id,
            self.abort_injected_at_step_id,
            self.rollback_decision,
        )
        if any(STABLE_ID.fullmatch(value) is None for value in identifiers):
            raise ValueError("upgrade simulation identifier is invalid")
        if any(
            SHA256.fullmatch(value) is None
            for value in (self.plan_digest, self.request_fingerprint, self.simulation_digest)
        ):
            raise ValueError("upgrade simulation digest is invalid")
        if self.source_run_version < 1 or len(self.steps) != 8:
            raise ValueError("upgrade simulation source or timeline is invalid")
        if tuple(item.sequence for item in self.steps) != tuple(range(1, 9)):
            raise ValueError("upgrade simulation timeline is unordered")
        if len(self.impacted_service_ids) != 2 or len(self.post_verification_check_ids) != 6:
            raise ValueError("upgrade simulation evidence is incomplete")
        if not 1 <= self.estimated_downtime_minutes <= 240:
            raise ValueError("upgrade simulation downtime is invalid")
        if self.state is not UpgradeSimulationState.PASSED or not self.isolated_target:
            raise ValueError("upgrade simulation did not pass in isolation")
        if any(
            (
                self.production_authorized,
                self.artifact_acquisition_performed,
                self.database_migration_performed,
                self.service_restart_performed,
                self.traffic_switch_performed,
                self.active_restore_performed,
                self.secret_resolution_performed,
                self.network_request_performed,
                self.model_inference_performed,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("upgrade simulation performed a forbidden operation")
