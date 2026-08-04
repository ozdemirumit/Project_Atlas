from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.release_preflight import SHA256_PATTERN, DeploymentProfile


class DataPlanState(StrEnum):
    PASSED = "passed"


class DataTargetState(StrEnum):
    EMPTY = "empty"
    REUSABLE = "reusable"


class MigrationCompatibility(StrEnum):
    EXPAND = "expand"


class BackupApplicability(StrEnum):
    NOT_APPLICABLE_CLEAN_INSTALL = "not_applicable_clean_install"


class DataInitializationState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DataStateDisposition(StrEnum):
    PUBLISHED = "published"
    REUSED = "reused"


@dataclass(frozen=True, slots=True)
class BootstrapMigrationSpec:
    migration_id: str
    sequence: int
    sha256: str
    from_revision: str
    to_revision: str
    compatibility: MigrationCompatibility
    reversible: bool
    destructive: bool
    recovery_code: str
    expected_object_count: int

    def __post_init__(self) -> None:
        for value, label in (
            (self.migration_id, "migration id"),
            (self.from_revision, "migration from revision"),
            (self.to_revision, "migration to revision"),
            (self.recovery_code, "migration recovery code"),
        ):
            validate_stable_identifier(value, label)
        if self.sequence < 1 or not SHA256_PATTERN.fullmatch(self.sha256):
            raise ValueError("migration sequence or checksum is invalid")
        if self.destructive or not self.reversible:
            raise ValueError("clean initialization contains an unsafe migration")
        if not 1 <= self.expected_object_count <= 1000:
            raise ValueError("migration object count is outside platform bounds")


@dataclass(frozen=True, slots=True)
class BootstrapDataPlan:
    schema_version: str
    release_id: str
    profile: DeploymentProfile
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
    target_state: DataTargetState
    state: DataPlanState
    result_code: str
    migrations: tuple[BootstrapMigrationSpec, ...]
    backup_applicability: BackupApplicability
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.schema_version != "atlas.bootstrap-data-plan.v1":
            raise ValueError("bootstrap data plan schema is unsupported")
        for value, label in (
            (self.release_id, "release id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.site_id, "site id"),
            (self.target_id, "data target id"),
            (self.target_kind, "data target kind"),
            (self.current_revision, "current schema revision"),
            (self.target_revision, "target schema revision"),
            (self.result_code, "data plan result code"),
        ):
            validate_stable_identifier(value, label)
        digests = (
            self.configuration_digest,
            self.trust_plan_digest,
            self.migration_artifact_digest,
            self.data_plan_digest,
        )
        if any(not SHA256_PATTERN.fullmatch(value) for value in digests):
            raise ValueError("bootstrap data plan digest is invalid")
        if self.generated_at.tzinfo is None or not 1 <= len(self.migrations) <= 64:
            raise ValueError("bootstrap data plan metadata is invalid")
        sequences = tuple(item.sequence for item in self.migrations)
        ids = tuple(item.migration_id for item in self.migrations)
        checksums = tuple(item.sha256 for item in self.migrations)
        if sequences != tuple(range(1, len(self.migrations) + 1)):
            raise ValueError("migration catalog order is invalid")
        if len(ids) != len(set(ids)) or len(checksums) != len(set(checksums)):
            raise ValueError("migration catalog contains duplicates")
        expected_from = self.current_revision
        for migration in self.migrations:
            if migration.from_revision != expected_from:
                raise ValueError("migration revision chain is invalid")
            expected_from = migration.to_revision
        if expected_from != self.target_revision:
            raise ValueError("migration catalog does not reach the target revision")
        if self.target_state not in {DataTargetState.EMPTY, DataTargetState.REUSABLE}:
            raise ValueError("data target state is unsafe")


@dataclass(frozen=True, slots=True)
class DataStateEvidence:
    evidence_id: str
    sha256: str
    size_bytes: int
    disposition: DataStateDisposition

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_id, "data evidence id")
        if not SHA256_PATTERN.fullmatch(self.sha256) or self.size_bytes < 1:
            raise ValueError("data state evidence is invalid")


@dataclass(frozen=True, slots=True)
class DataInitializationExecution:
    execution_id: str
    phase_id: str
    release_id: str
    profile: DeploymentProfile
    configuration_digest: str
    trust_plan_digest: str
    data_schema_version: str
    data_plan_digest: str
    migration_artifact_digest: str
    target_id: str
    from_revision: str
    to_revision: str
    state: DataInitializationState
    result_code: str
    started_at: datetime
    completed_at: datetime | None
    migration_count: int
    verified_object_count: int
    lock_acquired: bool
    backup_applicability: BackupApplicability
    evidence: tuple[DataStateEvidence, ...]

    def __post_init__(self) -> None:
        for value, label in (
            (self.execution_id, "execution id"),
            (self.phase_id, "phase id"),
            (self.release_id, "release id"),
            (self.data_schema_version, "data schema version"),
            (self.target_id, "data target id"),
            (self.from_revision, "data from revision"),
            (self.to_revision, "data to revision"),
            (self.result_code, "data result code"),
        ):
            validate_stable_identifier(value, label)
        if (
            self.phase_id != "phase.data"
            or self.data_schema_version != "atlas.bootstrap-data-plan.v1"
        ):
            raise ValueError("data initialization phase identity is invalid")
        digests = (
            self.configuration_digest,
            self.trust_plan_digest,
            self.data_plan_digest,
            self.migration_artifact_digest,
        )
        if any(not SHA256_PATTERN.fullmatch(value) for value in digests):
            raise ValueError("data initialization digest is invalid")
        if self.started_at.tzinfo is None or (
            self.completed_at is not None and self.completed_at.tzinfo is None
        ):
            raise ValueError("data initialization timestamps must be timezone-aware")
        if self.state is DataInitializationState.RUNNING:
            if (
                self.completed_at
                or self.migration_count
                or self.verified_object_count
                or self.evidence
            ):
                raise ValueError("running data initialization cannot contain final evidence")
        elif self.completed_at is None or self.completed_at < self.started_at:
            raise ValueError("finished data initialization requires a valid completion time")
        if self.state is DataInitializationState.COMPLETED:
            if (
                self.migration_count < 1
                or self.verified_object_count < 1
                or not self.lock_acquired
                or len(self.evidence) != 1
            ):
                raise ValueError("completed data initialization evidence is incomplete")
        elif self.migration_count or self.verified_object_count or self.evidence:
            raise ValueError("failed data initialization cannot contain verified evidence")


@dataclass(frozen=True, slots=True)
class DataInitializationReceipt:
    migration_count: int
    verified_object_count: int
    evidence: tuple[DataStateEvidence, ...]

    def __post_init__(self) -> None:
        if self.migration_count < 1 or self.verified_object_count < 1 or len(self.evidence) != 1:
            raise ValueError("data initialization receipt is incomplete")
