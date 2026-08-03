from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class HealthCheckRunState(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HealthCheckTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class ObservationState(StrEnum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class FreshnessState(StrEnum):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class HealthCheckSchedule:
    interval_minutes: int
    anchor_at: datetime

    def __post_init__(self) -> None:
        if self.anchor_at.tzinfo is None:
            raise ValueError("schedule anchor_at must be timezone-aware")
        if self.interval_minutes < 1:
            raise ValueError("schedule interval must be positive")

    def due_times(self, at: datetime) -> tuple[datetime, datetime]:
        if at.tzinfo is None:
            raise ValueError("schedule evaluation time must be timezone-aware")
        interval = timedelta(minutes=self.interval_minutes)
        if at < self.anchor_at:
            return self.anchor_at - interval, self.anchor_at
        elapsed = at - self.anchor_at
        periods = elapsed // interval
        last_due = self.anchor_at + periods * interval
        return last_due, last_due + interval


@dataclass(frozen=True, slots=True)
class HealthCheckLimits:
    timeout_seconds: float
    max_steps: int
    max_evidence_records: int
    max_targets: int = 1

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout must be positive")
        if min(self.max_steps, self.max_evidence_records, self.max_targets) < 1:
            raise ValueError("health-check limits must be positive")


@dataclass(frozen=True, slots=True)
class HealthThreshold:
    metric: str
    warning_condition: str
    critical_condition: str
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class HealthCheckDefinition:
    definition_id: str
    version: int
    title: str
    owner: str
    enabled: bool
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    connector_id: str
    connector_version: str
    capability_id: str
    capability_class: str
    schedule: HealthCheckSchedule
    thresholds: tuple[HealthThreshold, ...]
    limits: HealthCheckLimits
    evidence_requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("definition version must be positive")
        if self.capability_class != "C1":
            raise ValueError("this health-check slice permits only C1 capabilities")
        if not self.thresholds or not self.evidence_requirements:
            raise ValueError("health-check definitions require thresholds and evidence")


@dataclass(frozen=True, slots=True)
class HealthCheckEvidence:
    reference: str
    source: str
    source_version: str
    observed_at: datetime
    freshness: FreshnessState
    trust_basis: str

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("evidence observed_at must be timezone-aware")
        if not self.reference or not self.trust_basis:
            raise ValueError("evidence identity and trust basis are required")


@dataclass(frozen=True, slots=True)
class HealthObservation:
    observation_id: str
    target_id: str
    component: str
    metric: str
    value: str
    unit: str | None
    state: ObservationState
    observed_at: datetime
    freshness: FreshnessState
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observation time must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("health observations require evidence")


@dataclass(frozen=True, slots=True)
class HealthCheckFinding:
    finding_id: str
    severity: ObservationState
    title: str
    summary: str
    observation_ids: tuple[str, ...]
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.severity is ObservationState.NORMAL:
            raise ValueError("normal observations are not findings")
        if not self.observation_ids or not self.evidence_references:
            raise ValueError("findings require observations and evidence")


@dataclass(frozen=True, slots=True)
class HealthCheckRun:
    run_id: str
    definition_id: str
    definition_version: int
    connector_id: str
    connector_version: str
    capability_id: str
    target_id: str
    trigger: HealthCheckTrigger
    requested_by: str
    started_at: datetime
    completed_at: datetime
    state: HealthCheckRunState
    step_count: int
    observations: tuple[HealthObservation, ...]
    findings: tuple[HealthCheckFinding, ...]
    evidence: tuple[HealthCheckEvidence, ...]
    partial_reasons: tuple[str, ...]
    unknowns: tuple[str, ...]
    safety_notice: str

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("run timestamps must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("run completion cannot precede start")
        evidence_ids = {item.reference for item in self.evidence}
        referenced = {
            reference
            for references in (
                *(item.evidence_references for item in self.observations),
                *(item.evidence_references for item in self.findings),
            )
            for reference in references
        }
        if not referenced <= evidence_ids:
            raise ValueError("run contains unresolved evidence references")
        if self.state is not HealthCheckRunState.COMPLETED and not (
            self.partial_reasons or self.unknowns
        ):
            raise ValueError("non-completed runs must explain incomplete knowledge")


@dataclass(frozen=True, slots=True)
class HealthCheckScheduleStatus:
    definition_id: str
    enabled: bool
    interval_minutes: int
    last_due_at: datetime
    next_due_at: datetime


@dataclass(frozen=True, slots=True)
class HealthCheckOverview:
    generated_at: datetime
    data_profile: str
    definitions: tuple[HealthCheckDefinition, ...]
    schedules: tuple[HealthCheckScheduleStatus, ...]
    latest_runs: tuple[HealthCheckRun, ...]
    safety_notice: str
