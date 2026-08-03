from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.health_checks.application.ports import (
    HealthCheckExecutionResult,
    HealthCheckExecutor,
)
from atlas.modules.health_checks.domain.models import (
    HealthCheckDefinition,
    HealthCheckOverview,
    HealthCheckRun,
    HealthCheckRunState,
    HealthCheckScheduleStatus,
    HealthCheckTrigger,
)

HEALTH_CHECK_RESOURCE_ID = "resource.health-check.storage.synthetic"
ALLOWED_CAPABILITIES = frozenset(
    {
        "hitachi.opscenter.storage.hardware.read",
        "hitachi.opscenter.storage.capacity.read",
    }
)
SAFETY_NOTICE = (
    "Read-only decision support. Health-check results do not authorize or perform an "
    "infrastructure change."
)


@dataclass(frozen=True, slots=True)
class HealthCheckAccessContext:
    subject_id: str
    actor_type: str
    authentication_method: str
    assurance_level: str
    organization_id: str
    environment_id: str
    site_id: str
    resource_id: str
    correlation_id: str
    decision_id: str
    requested_at: datetime


class HealthCheckOperationsError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class HealthCheckService:
    def __init__(
        self,
        *,
        definitions: tuple[HealthCheckDefinition, ...],
        latest_runs: tuple[HealthCheckRun, ...],
        executor: HealthCheckExecutor,
        audit_sink: AuditSink,
    ) -> None:
        if len({item.definition_id for item in definitions}) != len(definitions):
            raise ValueError("health-check definition identifiers must be unique")
        self._definitions = {item.definition_id: item for item in definitions}
        self._latest_runs = {item.definition_id: item for item in latest_runs}
        self._executor = executor
        self._audit_sink = audit_sink

    async def get_overview(self, context: HealthCheckAccessContext) -> HealthCheckOverview:
        self._validate_scope(context)
        definitions = tuple(self._definitions.values())
        schedules = tuple(
            HealthCheckScheduleStatus(
                definition_id=definition.definition_id,
                enabled=definition.enabled,
                interval_minutes=definition.schedule.interval_minutes,
                last_due_at=definition.schedule.due_times(context.requested_at)[0],
                next_due_at=definition.schedule.due_times(context.requested_at)[1],
            )
            for definition in definitions
        )
        overview = HealthCheckOverview(
            generated_at=context.requested_at,
            data_profile="synthetic_lab",
            definitions=definitions,
            schedules=schedules,
            latest_runs=tuple(
                self._latest_runs[item.definition_id]
                for item in definitions
                if item.definition_id in self._latest_runs
            ),
            safety_notice=SAFETY_NOTICE,
        )
        await self._record_audit(
            context,
            event_type="atlas.health_check.overview.read",
            permission_id="health-check.overview.read",
            outcome="succeeded",
            result_code="health_check_overview_returned",
        )
        return overview

    async def run(
        self,
        definition_id: str,
        *,
        trigger: HealthCheckTrigger,
        context: HealthCheckAccessContext,
    ) -> HealthCheckRun:
        self._validate_scope(context)
        definition = self._definitions.get(definition_id)
        if definition is None:
            raise HealthCheckOperationsError(
                "health_check_unavailable", "The requested health check is unavailable."
            )
        if not definition.enabled:
            raise HealthCheckOperationsError(
                "health_check_disabled", "The requested health check is not enabled."
            )
        if definition.capability_id not in ALLOWED_CAPABILITIES:
            raise HealthCheckOperationsError(
                "health_check_capability_denied",
                "The requested health check cannot be dispatched.",
            )
        if definition.limits.max_targets < 1:
            raise HealthCheckOperationsError(
                "health_check_target_limit", "The health-check target limit is invalid."
            )

        await self._record_audit(
            context,
            event_type="atlas.health_check.run.accepted",
            permission_id="health-check.run.create",
            outcome="accepted",
            result_code="health_check_run_accepted",
        )

        try:
            result = await asyncio.wait_for(
                self._executor.execute(definition, started_at=context.requested_at),
                timeout=definition.limits.timeout_seconds,
            )
        except TimeoutError:
            result = HealthCheckExecutionResult(
                state=HealthCheckRunState.TIMED_OUT,
                completed_at=context.requested_at,
                step_count=0,
                observations=(),
                findings=(),
                evidence=(),
                partial_reasons=("The connector read exceeded the definition timeout.",),
                unknowns=("Target health is unknown because the read did not complete.",),
            )
        except Exception as exc:
            raise HealthCheckOperationsError(
                "health_check_execution_failed", "The health-check execution failed safely."
            ) from exc

        result = self._enforce_result_limits(definition, result, context.requested_at)
        run = HealthCheckRun(
            run_id=f"run_{uuid4().hex}",
            definition_id=definition.definition_id,
            definition_version=definition.version,
            connector_id=definition.connector_id,
            connector_version=definition.connector_version,
            capability_id=definition.capability_id,
            target_id=definition.target_id,
            trigger=trigger,
            requested_by=context.subject_id,
            started_at=context.requested_at,
            completed_at=result.completed_at,
            state=result.state,
            step_count=result.step_count,
            observations=result.observations,
            findings=result.findings,
            evidence=result.evidence,
            partial_reasons=result.partial_reasons,
            unknowns=result.unknowns,
            safety_notice=SAFETY_NOTICE,
        )
        await self._record_audit(
            context,
            event_type="atlas.health_check.run.completed",
            permission_id="health-check.run.create",
            outcome=run.state.value,
            result_code=f"health_check_run_{run.state.value}",
        )
        self._latest_runs[definition.definition_id] = run
        return run

    @staticmethod
    def _enforce_result_limits(
        definition: HealthCheckDefinition,
        result: HealthCheckExecutionResult,
        requested_at: datetime,
    ) -> HealthCheckExecutionResult:
        exceeded = []
        if result.step_count > definition.limits.max_steps:
            exceeded.append("step")
        if len(result.evidence) > definition.limits.max_evidence_records:
            exceeded.append("evidence")
        if not exceeded:
            return result
        return HealthCheckExecutionResult(
            state=HealthCheckRunState.FAILED,
            completed_at=max(result.completed_at, requested_at),
            step_count=min(result.step_count, definition.limits.max_steps),
            observations=(),
            findings=(),
            evidence=(),
            partial_reasons=(
                f"The connector result exceeded the configured {' and '.join(exceeded)} budget.",
            ),
            unknowns=("Target health is unknown because the bounded result was rejected.",),
        )

    @staticmethod
    def _validate_scope(context: HealthCheckAccessContext) -> None:
        if context.resource_id != HEALTH_CHECK_RESOURCE_ID:
            raise HealthCheckOperationsError(
                "health_check_scope_mismatch",
                "The health-check target is outside the authorized scope.",
            )

    async def _record_audit(
        self,
        context: HealthCheckAccessContext,
        *,
        event_type: str,
        permission_id: str,
        outcome: str,
        result_code: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level=context.assurance_level,
                permission_id=permission_id,
                resource_type="resource.health-check",
                scope_reference="/".join(
                    (
                        context.organization_id,
                        context.environment_id,
                        context.site_id,
                        context.resource_id,
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
            )
        )
