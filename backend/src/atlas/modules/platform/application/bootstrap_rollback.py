"""ATLAS-038 SS25/SS33: Rollback foundation application service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.platform.application.bootstrap_rollback_ports import (
    BootstrapRollbackRepository,
)
from atlas.modules.platform.domain.bootstrap_rollback import (
    ComponentVersionCompatibility,
    RollbackAttempt,
    RollbackOutcome,
    RollbackPlan,
    RollbackSupportDeclaration,
    SchemaCompatibilityCheck,
)


class BootstrapRollbackError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BootstrapRollbackService:
    def __init__(
        self,
        *,
        repository: BootstrapRollbackRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def plan_rollback(
        self,
        *,
        plan_id: str,
        release_id: str,
        target_release_id: str,
        support: RollbackSupportDeclaration,
        schema_check: SchemaCompatibilityCheck,
        component_compatibility: tuple[ComponentVersionCompatibility, ...],
        configuration_rollback_independent: bool,
        secret_rollback_independent: bool,
        artifacts_available_until: datetime,
        correlation_id: str,
    ) -> RollbackPlan:
        try:
            plan = RollbackPlan(
                plan_id=plan_id,
                release_id=release_id,
                target_release_id=target_release_id,
                support=support,
                schema_check=schema_check,
                component_compatibility=component_compatibility,
                configuration_rollback_independent=configuration_rollback_independent,
                secret_rollback_independent=secret_rollback_independent,
                artifacts_available_until=artifacts_available_until,
                generated_at=self._clock(),
            )
        except ValueError as error:
            raise BootstrapRollbackError("bootstrap_rollback_plan_invalid") from error
        await self._repository.save_plan(plan)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.platform.bootstrap-rollback.planned",
            scope_reference=plan_id,
            result_code="bootstrap_rollback_planned",
        )
        return plan

    async def record_attempt(
        self,
        *,
        attempt_id: str,
        plan_id: str,
        started_at: datetime,
        outcome: RollbackOutcome,
        post_rollback_health_check_passed: bool,
        post_rollback_security_check_passed: bool,
        failure_recovery_reference: str | None,
        correlation_id: str,
    ) -> RollbackAttempt:
        plan = await self._repository.get_plan(plan_id)
        if plan is None:
            raise BootstrapRollbackError("bootstrap_rollback_plan_unavailable")
        if outcome is RollbackOutcome.SUCCEEDED and not plan.is_permitted:
            raise BootstrapRollbackError("bootstrap_rollback_not_permitted")
        try:
            attempt = RollbackAttempt(
                attempt_id=attempt_id,
                plan_id=plan_id,
                started_at=started_at,
                completed_at=self._clock(),
                outcome=outcome,
                post_rollback_health_check_passed=post_rollback_health_check_passed,
                post_rollback_security_check_passed=post_rollback_security_check_passed,
                failure_recovery_reference=failure_recovery_reference,
            )
        except ValueError as error:
            raise BootstrapRollbackError("bootstrap_rollback_attempt_invalid") from error
        await self._repository.save_attempt(attempt)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.platform.bootstrap-rollback.attempted",
            scope_reference=plan_id,
            result_code=(
                "bootstrap_rollback_succeeded"
                if outcome is RollbackOutcome.SUCCEEDED
                else "bootstrap_rollback_failed"
            ),
        )
        return attempt

    async def _audit(
        self, *, correlation_id: str, event_type: str, scope_reference: str, result_code: str
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=None,
                actor_type=None,
                authentication_method=None,
                assurance_level=None,
                permission_id="platform.bootstrap-state.manage",
                resource_type="resource.platform.bootstrap-rollback",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
            )
        )
