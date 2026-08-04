from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.domain.bootstrap_invalidation import (
    BootstrapInvalidationPreview,
    BootstrapInvalidationState,
    compare_bootstrap_run,
)
from atlas.modules.platform.domain.bootstrap_state import BootstrapRunIdentity, BootstrapRunRecord


class BootstrapInvalidationScopeError(RuntimeError):
    pass


class BootstrapInvalidationService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        environment_id: str,
        site_id: str,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._environment_id = environment_id
        self._site_id = site_id
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def preview(
        self,
        *,
        actor: AuthenticatedSubject,
        candidate: BootstrapRunIdentity,
        correlation_id: str,
    ) -> BootstrapInvalidationPreview:
        if (
            candidate.organization_id != actor.organization_id
            or candidate.environment_id != self._environment_id
            or candidate.site_id != self._site_id
        ):
            await self._audit_denial(actor, correlation_id)
            raise BootstrapInvalidationScopeError(
                "bootstrap invalidation scope does not match actor"
            )
        record = await self._repository.get_current(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
        )
        generated_at = self._clock()
        if record is None:
            preview = BootstrapInvalidationPreview(
                preview_id=f"bootstrap-invalidation.{uuid4().hex}",
                schema_version="atlas.bootstrap-invalidation-preview.v1",
                state=BootstrapInvalidationState.EMPTY,
                source_run_id=None,
                source_run_version=None,
                changes=(),
                earliest_affected_phase_id=None,
                reusable_checkpoint_phase_ids=(),
                invalidated_checkpoint_phase_ids=(),
                downstream_phase_ids=(),
                remediation="Initialize governed bootstrap state before evaluating resume drift.",
                generated_at=generated_at,
                correlation_id=correlation_id,
            )
        else:
            preview = self._compare(
                record.identity, candidate, record, generated_at, correlation_id
            )
        await self._audit_read(actor, preview)
        return preview

    def _compare(
        self,
        current: BootstrapRunIdentity,
        candidate: BootstrapRunIdentity,
        record: BootstrapRunRecord,
        generated_at: datetime,
        correlation_id: str,
    ) -> BootstrapInvalidationPreview:
        impact = compare_bootstrap_run(current, candidate, record)
        if impact.earliest_affected_phase_id is None:
            state = BootstrapInvalidationState.UNCHANGED
            remediation = None
        else:
            state = BootstrapInvalidationState.DRIFTED
            remediation = (
                "Create a new governed plan and resume only from the earliest affected phase after "
                "human review."
            )
        return BootstrapInvalidationPreview(
            preview_id=f"bootstrap-invalidation.{uuid4().hex}",
            schema_version="atlas.bootstrap-invalidation-preview.v1",
            state=state,
            source_run_id=record.run_id,
            source_run_version=record.version,
            changes=impact.changes,
            earliest_affected_phase_id=impact.earliest_affected_phase_id,
            reusable_checkpoint_phase_ids=impact.reusable_checkpoint_phase_ids,
            invalidated_checkpoint_phase_ids=impact.invalidated_checkpoint_phase_ids,
            downstream_phase_ids=impact.downstream_phase_ids,
            remediation=remediation,
            generated_at=generated_at,
            correlation_id=correlation_id,
        )

    async def _audit_read(
        self, actor: AuthenticatedSubject, preview: BootstrapInvalidationPreview
    ) -> None:
        await self._audit_sink.record(
            self._audit_record(
                actor=actor,
                correlation_id=preview.correlation_id,
                outcome="succeeded",
                result_code=f"bootstrap_invalidation_{preview.state.value}",
                scope_reference=f"{actor.organization_id}/{self._environment_id}/{self._site_id}/domain.platform/resource.platform.bootstrap-invalidation/C0",
                target_metadata=(("change_count", str(len(preview.changes))),),
            )
        )

    async def _audit_denial(self, actor: AuthenticatedSubject, correlation_id: str) -> None:
        await self._audit_sink.record(
            self._audit_record(
                actor=actor,
                correlation_id=correlation_id,
                outcome="denied",
                result_code="bootstrap_invalidation_scope_mismatch",
                scope_reference="scope.redacted",
                target_metadata=(),
            )
        )

    def _audit_record(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        outcome: str,
        result_code: str,
        scope_reference: str,
        target_metadata: tuple[tuple[str, str], ...],
    ) -> AuditRecord:
        return AuditRecord(
            event_id=f"evt_{uuid4().hex}",
            event_type="atlas.platform.bootstrap-invalidation.read",
            schema_version="1.0",
            producer="atlas-api",
            producer_version=__version__,
            occurred_at=self._clock(),
            correlation_id=correlation_id,
            subject_id=actor.subject_id,
            actor_type=actor.kind.value,
            authentication_method=actor.authentication_method.value,
            assurance_level=actor.assurance_level.value,
            permission_id="platform.bootstrap-invalidation.preview",
            resource_type="resource.platform.bootstrap-invalidation",
            scope_reference=scope_reference,
            decision_id=None,
            outcome=outcome,
            result_code=result_code,
            target_metadata=target_metadata,
        )
