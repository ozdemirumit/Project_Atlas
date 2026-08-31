from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from atlas.modules.connectors.vendors.commvault.client import (
    CommvaultClient,
    CommvaultConnectorError,
)
from atlas.modules.connectors.vendors.commvault.domain import CommvaultJob, CommvaultJobStatus
from atlas.modules.health_checks.application.ports import HealthCheckExecutionResult
from atlas.modules.health_checks.domain.models import (
    FreshnessState,
    HealthCheckDefinition,
    HealthCheckEvidence,
    HealthCheckFinding,
    HealthCheckRunState,
    HealthObservation,
    ObservationState,
)

JOB_STATUS_DEFINITION_ID = "health-check.backup.commvault-job-status"

_SAFE_CONNECTOR_ERROR_CODES = frozenset(
    {
        "malformed_vendor_response",
        "target_timeout",
        "target_unavailable",
        "vendor_permission_denied",
        "vendor_rate_limited",
        "vendor_response_limit_exceeded",
    }
)
_OBSERVATION_STATE: dict[CommvaultJobStatus, ObservationState] = {
    # In-progress or successfully-terminal states: nothing to flag.
    CommvaultJobStatus.RUNNING: ObservationState.NORMAL,
    CommvaultJobStatus.WAITING: ObservationState.NORMAL,
    CommvaultJobStatus.PENDING: ObservationState.NORMAL,
    CommvaultJobStatus.QUEUED: ObservationState.NORMAL,
    CommvaultJobStatus.CLEANUP: ObservationState.NORMAL,
    CommvaultJobStatus.COMPLETED: ObservationState.NORMAL,
    CommvaultJobStatus.COMMITTED: ObservationState.NORMAL,
    # Transient or degraded-but-not-failed states worth surfacing.
    CommvaultJobStatus.SUSPEND: ObservationState.WARNING,
    CommvaultJobStatus.SUSPENDED: ObservationState.WARNING,
    CommvaultJobStatus.KILL_PENDING: ObservationState.WARNING,
    CommvaultJobStatus.INTERRUPT_PENDING: ObservationState.WARNING,
    CommvaultJobStatus.INTERRUPTED: ObservationState.WARNING,
    CommvaultJobStatus.RUNNING_CANNOT_BE_VERIFIED: ObservationState.WARNING,
    CommvaultJobStatus.COMPLETED_WITH_WARNINGS: ObservationState.WARNING,
    # Definite failure states.
    CommvaultJobStatus.ABNORMAL_TERMINATED: ObservationState.CRITICAL,
    CommvaultJobStatus.COMPLETED_WITH_ERRORS: ObservationState.CRITICAL,
    CommvaultJobStatus.FAILED: ObservationState.CRITICAL,
    CommvaultJobStatus.FAILED_TO_START: ObservationState.CRITICAL,
    CommvaultJobStatus.KILLED: ObservationState.CRITICAL,
    CommvaultJobStatus.UNKNOWN: ObservationState.UNKNOWN,
}


class CommvaultJobHealthExecutor:
    """Executes the bounded, read-only Commvault recent-backup-job-status check."""

    def __init__(
        self,
        *,
        client: CommvaultClient,
        capability_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._capability_id = capability_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult:
        self._validate_definition(definition)
        if definition.limits.max_steps < 1 or definition.limits.max_evidence_records < 1:
            return self._failed_result(
                started_at=started_at,
                step_count=0,
                partial_reason="The definition budget cannot contain a job-status read.",
                unknown="Job health is unknown because the definition budget is insufficient.",
            )

        try:
            result = await self._client.read_job_status()
        except CommvaultConnectorError as exc:
            return self._failed_result(
                started_at=started_at,
                step_count=1,
                partial_reason=self._connector_failure_reason(exc),
                unknown="Job health is unknown because job status could not be read.",
            )

        if len(result.evidence_references) > definition.limits.max_evidence_records:
            return self._failed_result(
                started_at=started_at,
                step_count=1,
                partial_reason="The job-status evidence exceeded the definition budget.",
                unknown="Job health is unknown because the bounded result was rejected.",
            )

        evidence = [
            HealthCheckEvidence(
                reference=reference,
                source="Commvault recent-job-status read",
                source_version=definition.connector_version,
                observed_at=result.observed_at,
                freshness=FreshnessState.CURRENT,
                trust_basis="Digest-only evidence from an allowlisted C1 REST API response",
            )
            for reference in result.evidence_references
        ]
        evidence_refs = tuple(item.reference for item in evidence)
        partial_reasons: list[str] = []
        unknowns: list[str] = []

        job_budget = min(definition.limits.max_targets, len(result.jobs))
        selected_jobs = result.jobs[:job_budget]
        if len(result.jobs) > job_budget:
            partial_reasons.append("Additional jobs were omitted by the definition target budget.")
            unknowns.append("Health is unknown for jobs outside the bounded execution set.")
        if not result.jobs:
            partial_reasons.append("No backup jobs were returned in the lookup window.")
            unknowns.append("No job status could be evaluated.")

        observations: list[HealthObservation] = []
        findings: list[HealthCheckFinding] = []
        for job in selected_jobs:
            state = _OBSERVATION_STATE.get(job.status, ObservationState.UNKNOWN)
            identity = self._identity(str(job.job_id))
            observation_id = f"observation.commvault.job.{identity}"
            observation = HealthObservation(
                observation_id=observation_id,
                target_id=f"{definition.target_id}/{job.job_id}",
                component=f"client:{job.client_name}/subclient:{job.subclient_name}",
                metric="job.status",
                value=job.status.value,
                unit=None,
                state=state,
                observed_at=result.observed_at,
                freshness=FreshnessState.CURRENT,
                evidence_references=evidence_refs,
            )
            observations.append(observation)
            if state is ObservationState.NORMAL:
                continue
            findings.append(
                self._finding(job=job, identity=identity, state=state, evidence_refs=evidence_refs)
            )

        run_state = (
            HealthCheckRunState.FAILED
            if not result.jobs
            else HealthCheckRunState.PARTIAL
            if partial_reasons
            else HealthCheckRunState.COMPLETED
        )

        return HealthCheckExecutionResult(
            state=run_state,
            completed_at=self._completed_at(started_at),
            step_count=1,
            observations=tuple(observations),
            findings=tuple(findings),
            evidence=tuple(evidence),
            partial_reasons=tuple(dict.fromkeys(partial_reasons)),
            unknowns=tuple(dict.fromkeys(unknowns)),
        )

    @staticmethod
    def _finding(
        *,
        job: CommvaultJob,
        identity: str,
        state: ObservationState,
        evidence_refs: tuple[str, ...],
    ) -> HealthCheckFinding:
        return HealthCheckFinding(
            finding_id=f"finding.commvault.job.{identity}",
            severity=state,
            title=f"Commvault job {job.job_id} reported a non-normal status",
            summary=(
                f"Job {job.job_id} for client {job.client_name} (subclient {job.subclient_name}) "
                f"reports status '{job.status.value}'."
            ),
            observation_ids=(f"observation.commvault.job.{identity}",),
            evidence_references=evidence_refs,
        )

    def _validate_definition(self, definition: HealthCheckDefinition) -> None:
        if (
            definition.definition_id != JOB_STATUS_DEFINITION_ID
            or definition.capability_id != self._capability_id
        ):
            raise ValueError("unsupported Commvault health-check definition")

    @staticmethod
    def _identity(*parts: str) -> str:
        normalized = "\x1f".join(parts).encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()[:20]

    @staticmethod
    def _connector_failure_reason(exc: CommvaultConnectorError) -> str:
        code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
        return f"The Commvault read failed safely ({code})."

    def _failed_result(
        self,
        *,
        started_at: datetime,
        step_count: int,
        partial_reason: str,
        unknown: str,
    ) -> HealthCheckExecutionResult:
        return HealthCheckExecutionResult(
            state=HealthCheckRunState.FAILED,
            completed_at=self._completed_at(started_at),
            step_count=step_count,
            observations=(),
            findings=(),
            evidence=(),
            partial_reasons=(partial_reason,),
            unknowns=(unknown,),
        )

    def _completed_at(self, started_at: datetime) -> datetime:
        return max(self._clock(), started_at)
