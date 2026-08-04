from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.domain.bootstrap_invalidation import (
    BootstrapInputChange,
    BootstrapInvalidationPreview,
    BootstrapInvalidationState,
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
        changes: list[BootstrapInputChange] = []
        for field, code, field_boundary in (
            ("release_id", "bootstrap.release.changed", "phase.acquire"),
            ("profile", "bootstrap.profile.changed", "phase.acquire"),
            ("plan_digest", "bootstrap.plan.changed", "phase.acquire"),
            ("resume_key", "bootstrap.resume-key.changed", "phase.acquire"),
            ("configuration_digest", "bootstrap.configuration.changed", "phase.configure"),
        ):
            old = getattr(current, field)
            new = getattr(candidate, field)
            old_value = old.value if hasattr(old, "value") else str(old)
            new_value = new.value if hasattr(new, "value") else str(new)
            if old_value != new_value:
                changes.append(
                    BootstrapInputChange(
                        field=field,
                        reason_code=code,
                        old_reference=self._safe_reference(field, old_value),
                        new_reference=self._safe_reference(field, new_value),
                        earliest_affected_phase_id=field_boundary,
                    )
                )
        if current.phase_ids != candidate.phase_ids:
            mismatch = next(
                (
                    index
                    for index, pair in enumerate(
                        zip(current.phase_ids, candidate.phase_ids, strict=False)
                    )
                    if pair[0] != pair[1]
                ),
                min(len(current.phase_ids), len(candidate.phase_ids)),
            )
            boundary_index = min(mismatch, len(current.phase_ids) - 1)
            changes.append(
                BootstrapInputChange(
                    field="phase_ids",
                    reason_code="bootstrap.phase-order.changed",
                    old_reference=self._safe_reference("phase_ids", current.phase_ids),
                    new_reference=self._safe_reference("phase_ids", candidate.phase_ids),
                    earliest_affected_phase_id=current.phase_ids[boundary_index],
                )
            )
        phase_positions = {phase_id: index for index, phase_id in enumerate(current.phase_ids)}
        earliest_boundary: str | None = min(
            (item.earliest_affected_phase_id for item in changes),
            key=lambda item: phase_positions.get(item, 0),
            default=None,
        )
        completed = record.completed_phase_ids
        if earliest_boundary is None:
            reusable = completed
            invalidated: tuple[str, ...] = ()
            downstream: tuple[str, ...] = ()
            state = BootstrapInvalidationState.UNCHANGED
            remediation = None
        else:
            boundary_index = phase_positions.get(earliest_boundary, 0)
            reusable = tuple(
                item for item in completed if phase_positions.get(item, 0) < boundary_index
            )
            invalidated = tuple(item for item in completed if item not in reusable)
            downstream = current.phase_ids[boundary_index:]
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
            changes=tuple(changes),
            earliest_affected_phase_id=earliest_boundary,
            reusable_checkpoint_phase_ids=reusable,
            invalidated_checkpoint_phase_ids=invalidated,
            downstream_phase_ids=downstream,
            remediation=remediation,
            generated_at=generated_at,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _safe_reference(field: str, value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
        return f"sha256:{sha256(field.encode() + b':' + encoded).hexdigest()}"

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
