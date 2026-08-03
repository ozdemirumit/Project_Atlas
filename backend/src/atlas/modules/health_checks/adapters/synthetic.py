from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from atlas.modules.health_checks.application.ports import HealthCheckExecutionResult
from atlas.modules.health_checks.domain.models import (
    FreshnessState,
    HealthCheckDefinition,
    HealthCheckEvidence,
    HealthCheckFinding,
    HealthCheckLimits,
    HealthCheckRun,
    HealthCheckRunState,
    HealthCheckSchedule,
    HealthCheckTrigger,
    HealthObservation,
    HealthThreshold,
    ObservationState,
)

CONTROLLER_DEFINITION_ID = "health-check.storage.controller-status"
CAPACITY_DEFINITION_ID = "health-check.storage.capacity-utilization"


def _reference(kind: str, content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"synthetic-hitachi-health://{kind}#sha256:{digest}"


def build_synthetic_health_check_definitions(
    *, organization_id: str, environment: str, anchor_at: datetime | None = None
) -> tuple[HealthCheckDefinition, ...]:
    anchor = anchor_at or datetime(2026, 8, 3, 0, 0, tzinfo=UTC)
    common = {
        "owner": "Storage Operations",
        "enabled": True,
        "organization_id": organization_id,
        "environment_id": f"environment.{environment}",
        "site_id": "site.local",
        "target_id": "target.hitachi.opscenter.lab",
        "connector_id": "connector.hitachi.opscenter.synthetic",
        "connector_version": "1.0.0",
        "capability_class": "C1",
    }
    return (
        HealthCheckDefinition(
            definition_id=CONTROLLER_DEFINITION_ID,
            version=1,
            title="Storage controller status",
            capability_id="hitachi.opscenter.storage.hardware.read",
            schedule=HealthCheckSchedule(interval_minutes=15, anchor_at=anchor),
            thresholds=(
                HealthThreshold(
                    metric="controller.status",
                    warning_condition="vendor status equals Warning",
                    critical_condition="vendor status equals Critical or Failed",
                ),
            ),
            limits=HealthCheckLimits(
                timeout_seconds=5.0,
                max_steps=3,
                max_evidence_records=8,
            ),
            evidence_requirements=(
                "Current hardware status for each allowlisted array",
                "Authorized event-log correlation for warning observations",
            ),
            **common,  # type: ignore[arg-type]
        ),
        HealthCheckDefinition(
            definition_id=CAPACITY_DEFINITION_ID,
            version=1,
            title="Storage capacity utilization",
            capability_id="hitachi.opscenter.storage.capacity.read",
            schedule=HealthCheckSchedule(interval_minutes=60, anchor_at=anchor),
            thresholds=(
                HealthThreshold(
                    metric="pool.utilization",
                    warning_condition="utilization is at least 75",
                    critical_condition="utilization is at least 90",
                    unit="percent",
                ),
            ),
            limits=HealthCheckLimits(
                timeout_seconds=5.0,
                max_steps=2,
                max_evidence_records=4,
            ),
            evidence_requirements=("Current capacity summary for each allowlisted array",),
            **common,  # type: ignore[arg-type]
        ),
    )


class SyntheticStorageHealthExecutor:
    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult:
        if definition.definition_id == CONTROLLER_DEFINITION_ID:
            return _controller_result(started_at)
        if definition.definition_id == CAPACITY_DEFINITION_ID:
            return _capacity_result(started_at)
        raise ValueError("unsupported synthetic health-check definition")


def _controller_result(observed_at: datetime) -> HealthCheckExecutionResult:
    normal_ref = _reference("controllers/g400", "CTL1=Normal|CTL2=Normal")
    warning_ref = _reference("controllers/b28", "CTL01=Warning|CTL02=Normal")
    evidence = (
        HealthCheckEvidence(
            reference=normal_ref,
            source="Hitachi Ops Center synthetic hardware fixture",
            source_version="11.0.x-contract.1",
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis="Documentation-derived allowlisted C1 response",
        ),
        HealthCheckEvidence(
            reference=warning_ref,
            source="Hitachi Ops Center synthetic hardware fixture",
            source_version="11.0.x-contract.1",
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis="Documentation-derived allowlisted C1 response",
        ),
    )
    observations = (
        HealthObservation(
            observation_id="observation.health.g400.controllers",
            target_id="asset.storage.lab.g400",
            component="Controllers",
            metric="controller.status",
            value="Normal",
            unit=None,
            state=ObservationState.NORMAL,
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            evidence_references=(normal_ref,),
        ),
        HealthObservation(
            observation_id="observation.health.b28.ctl01",
            target_id="asset.storage.lab.b28",
            component="CTL01",
            metric="controller.status",
            value="Warning",
            unit=None,
            state=ObservationState.WARNING,
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            evidence_references=(warning_ref,),
        ),
    )
    finding = HealthCheckFinding(
        finding_id="finding.health.b28.ctl01-warning",
        severity=ObservationState.WARNING,
        title="Controller warning requires correlation",
        summary=(
            "CTL01 reports Warning. Event-log evidence is unavailable, so persistence and cause "
            "remain unknown."
        ),
        observation_ids=("observation.health.b28.ctl01",),
        evidence_references=(warning_ref,),
    )
    return HealthCheckExecutionResult(
        state=HealthCheckRunState.PARTIAL,
        completed_at=observed_at,
        step_count=2,
        observations=observations,
        findings=(finding,),
        evidence=evidence,
        partial_reasons=("Authorized storage event-log evidence is not configured.",),
        unknowns=(
            "The warning duration and recurrence are unknown.",
            "No root cause or service outage is established by this check.",
        ),
    )


def _capacity_result(observed_at: datetime) -> HealthCheckExecutionResult:
    capacity_ref = _reference("capacity", "G400=62|B28=78")
    evidence = (
        HealthCheckEvidence(
            reference=capacity_ref,
            source="Hitachi Ops Center synthetic capacity fixture",
            source_version="11.0.x-contract.1",
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis="Documentation-derived allowlisted C1 response",
        ),
    )
    observations = (
        HealthObservation(
            observation_id="observation.capacity.g400",
            target_id="asset.storage.lab.g400",
            component="All pools",
            metric="pool.utilization",
            value="62",
            unit="percent",
            state=ObservationState.NORMAL,
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            evidence_references=(capacity_ref,),
        ),
        HealthObservation(
            observation_id="observation.capacity.b28",
            target_id="asset.storage.lab.b28",
            component="All pools",
            metric="pool.utilization",
            value="78",
            unit="percent",
            state=ObservationState.WARNING,
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            evidence_references=(capacity_ref,),
        ),
    )
    finding = HealthCheckFinding(
        finding_id="finding.capacity.b28.warning",
        severity=ObservationState.WARNING,
        title="Capacity utilization crossed the warning threshold",
        summary="VSP One B28 reports 78 percent utilization against a 75 percent threshold.",
        observation_ids=("observation.capacity.b28",),
        evidence_references=(capacity_ref,),
    )
    return HealthCheckExecutionResult(
        state=HealthCheckRunState.COMPLETED,
        completed_at=observed_at,
        step_count=1,
        observations=observations,
        findings=(finding,),
        evidence=evidence,
    )


def build_synthetic_latest_runs(
    definitions: tuple[HealthCheckDefinition, ...], *, generated_at: datetime | None = None
) -> tuple[HealthCheckRun, ...]:
    observed_at = generated_at or datetime.now(UTC)
    results = {
        CONTROLLER_DEFINITION_ID: _controller_result(observed_at),
        CAPACITY_DEFINITION_ID: _capacity_result(observed_at),
    }
    return tuple(
        HealthCheckRun(
            run_id=f"run.synthetic.{definition.definition_id.split('.')[-1]}.001",
            definition_id=definition.definition_id,
            definition_version=definition.version,
            connector_id=definition.connector_id,
            connector_version=definition.connector_version,
            capability_id=definition.capability_id,
            target_id=definition.target_id,
            trigger=HealthCheckTrigger.SCHEDULED,
            requested_by="service.health-check.scheduler",
            started_at=observed_at,
            completed_at=results[definition.definition_id].completed_at,
            state=results[definition.definition_id].state,
            step_count=results[definition.definition_id].step_count,
            observations=results[definition.definition_id].observations,
            findings=results[definition.definition_id].findings,
            evidence=results[definition.definition_id].evidence,
            partial_reasons=results[definition.definition_id].partial_reasons,
            unknowns=results[definition.definition_id].unknowns,
            safety_notice=(
                "Read-only decision support. This run does not authorize or perform an "
                "infrastructure change."
            ),
        )
        for definition in definitions
    )
