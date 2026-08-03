from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from atlas.api.schemas import ResponseMeta
from atlas.modules.health_checks.domain.models import HealthCheckOverview, HealthCheckRun


class HealthThresholdData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    warning_condition: str
    critical_condition: str
    unit: str | None


class HealthCheckLimitsData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_seconds: float
    max_steps: int
    max_evidence_records: int
    max_targets: int


class HealthCheckScheduleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interval_minutes: int
    anchor_at: datetime


class HealthCheckDefinitionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    schedule: HealthCheckScheduleData
    thresholds: list[HealthThresholdData]
    limits: HealthCheckLimitsData
    evidence_requirements: list[str]


class HealthCheckScheduleStatusData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition_id: str
    enabled: bool
    interval_minutes: int
    last_due_at: datetime
    next_due_at: datetime


class HealthCheckEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str
    source: str
    source_version: str
    observed_at: datetime
    freshness: str
    trust_basis: str


class HealthObservationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    target_id: str
    component: str
    metric: str
    value: str
    unit: str | None
    state: str
    observed_at: datetime
    freshness: str
    evidence_references: list[str]


class HealthCheckFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    severity: str
    title: str
    summary: str
    observation_ids: list[str]
    evidence_references: list[str]


class HealthCheckRunData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    definition_id: str
    definition_version: int
    connector_id: str
    connector_version: str
    capability_id: str
    target_id: str
    trigger: str
    requested_by: str
    started_at: datetime
    completed_at: datetime
    state: str
    step_count: int
    observations: list[HealthObservationData]
    findings: list[HealthCheckFindingData]
    evidence: list[HealthCheckEvidenceData]
    partial_reasons: list[str]
    unknowns: list[str]
    safety_notice: str

    @classmethod
    def from_domain(cls, run: HealthCheckRun) -> HealthCheckRunData:
        return cls.model_validate(run, from_attributes=True)


class HealthCheckOverviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    data_profile: str
    definitions: list[HealthCheckDefinitionData]
    schedules: list[HealthCheckScheduleStatusData]
    latest_runs: list[HealthCheckRunData]
    safety_notice: str

    @classmethod
    def from_domain(cls, overview: HealthCheckOverview) -> HealthCheckOverviewData:
        return cls.model_validate(overview, from_attributes=True)


class HealthCheckOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: HealthCheckOverviewData
    meta: ResponseMeta


class HealthCheckRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: HealthCheckRunData
    meta: ResponseMeta
