"""ATLAS-036 SS15/SS16: the application service that makes `ItsmCreationIntent` and
`ItsmConflictRecord` reachable. Distinct from `ItsmIntegrationService`'s own idempotency-key
replay (which only ever returns a cached profile-create result) -- SS15's creation-intent state
machine tracks an *outbound dispatch* to the external system, which can be genuinely ambiguous
(timeout, partial failure) in a way a same-process replay cache cannot represent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.itsm.application.dispatch_audit import (
    ItsmAuditEventKind,
    record_itsm_integration_event,
)
from atlas.modules.itsm.application.idempotency_conflict_ports import (
    ItsmConflictRecordRepository,
    ItsmCreationIntentRepository,
)
from atlas.modules.itsm.domain.idempotency_conflict import (
    ItsmConflictKind,
    ItsmConflictRecord,
    ItsmCreationIntent,
    ItsmCreationIntentState,
    ItsmFieldOwnership,
)

_TERMINAL_STATES = frozenset(
    {
        ItsmCreationIntentState.CONFIRMED_CREATED,
        ItsmCreationIntentState.RECONCILED_DUPLICATE,
        ItsmCreationIntentState.RECONCILED_NOT_CREATED,
    }
)


class ItsmIdempotencyConflictError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ItsmIdempotencyConflictService:
    def __init__(
        self,
        *,
        intent_repository: ItsmCreationIntentRepository,
        conflict_repository: ItsmConflictRecordRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._intents = intent_repository
        self._conflicts = conflict_repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def record_creation_intent(
        self,
        *,
        intent_id: str,
        idempotency_key: str,
        profile_id: str,
        operation: str,
        deduplication_signature: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> ItsmCreationIntent:
        existing = await self._intents.get_by_idempotency_key(
            profile_id=profile_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            await self._audit(
                existing.intent_id,
                actor=actor,
                correlation_id=correlation_id,
                event_kind=ItsmAuditEventKind.REPLAY,
                outcome="replayed",
            )
            return existing
        now = self._clock()
        try:
            intent = ItsmCreationIntent(
                intent_id=intent_id,
                idempotency_key=idempotency_key,
                profile_id=profile_id,
                operation=operation,
                deduplication_signature=deduplication_signature,
                state=ItsmCreationIntentState.PENDING,
                created_at=now,
                resolved_at=None,
                external_record_id=None,
            )
        except ValueError as error:
            raise ItsmIdempotencyConflictError("itsm_creation_intent_invalid") from error
        await self._intents.save(intent)
        await self._audit(
            intent.intent_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.CREATE,
            outcome="recorded",
        )
        return intent

    async def mark_dispatched(
        self, *, intent_id: str, actor: AuthenticatedSubject, correlation_id: str
    ) -> ItsmCreationIntent:
        intent = await self._require_intent(intent_id)
        if intent.state is not ItsmCreationIntentState.PENDING:
            raise ItsmIdempotencyConflictError("itsm_creation_intent_not_pending")
        updated = replace(intent, state=ItsmCreationIntentState.DISPATCHED)
        await self._intents.save(updated)
        await self._audit(
            intent_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.STATE_TRANSITION,
            outcome="dispatched",
        )
        return updated

    async def resolve_creation_intent(
        self,
        *,
        intent_id: str,
        resolution: ItsmCreationIntentState,
        external_record_id: str | None,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> ItsmCreationIntent:
        if resolution not in _TERMINAL_STATES:
            raise ItsmIdempotencyConflictError("itsm_creation_intent_resolution_not_terminal")
        intent = await self._require_intent(intent_id)
        if intent.state is not ItsmCreationIntentState.DISPATCHED:
            raise ItsmIdempotencyConflictError("itsm_creation_intent_not_dispatched")
        try:
            updated = replace(
                intent,
                state=resolution,
                resolved_at=self._clock(),
                external_record_id=external_record_id,
            )
        except ValueError as error:
            raise ItsmIdempotencyConflictError("itsm_creation_intent_resolution_invalid") from error
        await self._intents.save(updated)
        await self._audit(
            intent_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=(
                ItsmAuditEventKind.DUPLICATE
                if resolution is ItsmCreationIntentState.RECONCILED_DUPLICATE
                else ItsmAuditEventKind.STATE_TRANSITION
            ),
            outcome=resolution.value,
        )
        return updated

    async def record_conflict(
        self,
        *,
        conflict_id: str,
        profile_id: str,
        external_record_id: str,
        kind: ItsmConflictKind,
        last_known_source_version: str,
        observed_source_version: str,
        field_ownership: ItsmFieldOwnership,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> ItsmConflictRecord:
        if await self._conflicts.get(conflict_id) is not None:
            raise ItsmIdempotencyConflictError("itsm_conflict_already_recorded")
        try:
            conflict = ItsmConflictRecord(
                conflict_id=conflict_id,
                profile_id=profile_id,
                external_record_id=external_record_id,
                kind=kind,
                last_known_source_version=last_known_source_version,
                observed_source_version=observed_source_version,
                field_ownership=field_ownership,
                detected_at=self._clock(),
                resolution_summary=None,
                resolved_by=None,
                resolved_at=None,
            )
        except ValueError as error:
            raise ItsmIdempotencyConflictError("itsm_conflict_invalid") from error
        await self._conflicts.save(conflict)
        await self._audit(
            conflict_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.CONFLICT,
            outcome="detected",
        )
        return conflict

    async def resolve_conflict(
        self,
        *,
        conflict_id: str,
        resolution_summary: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> ItsmConflictRecord:
        conflict = await self._conflicts.get(conflict_id)
        if conflict is None:
            raise ItsmIdempotencyConflictError("itsm_conflict_not_found")
        if conflict.resolved_at is not None:
            raise ItsmIdempotencyConflictError("itsm_conflict_already_resolved")
        try:
            updated = replace(
                conflict,
                resolution_summary=resolution_summary,
                resolved_by=actor.subject_id,
                resolved_at=self._clock(),
            )
        except ValueError as error:
            raise ItsmIdempotencyConflictError("itsm_conflict_resolution_invalid") from error
        await self._conflicts.save(updated)
        await self._audit(
            conflict_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.RECONCILIATION,
            outcome="resolved",
        )
        return updated

    async def close(self) -> None:
        await self._intents.close()
        await self._conflicts.close()

    async def _require_intent(self, intent_id: str) -> ItsmCreationIntent:
        intent = await self._intents.get(intent_id)
        if intent is None:
            raise ItsmIdempotencyConflictError("itsm_creation_intent_not_found")
        return intent

    async def _audit(
        self,
        reference: str,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        event_kind: ItsmAuditEventKind,
        outcome: str,
    ) -> None:
        await record_itsm_integration_event(
            self._audit_sink,
            event_kind=event_kind,
            profile_reference=reference,
            actor_identity=actor.subject_id,
            is_automation=False,
            outcome=outcome,
            external_record_id=None,
            external_source_version=None,
            idempotency_key=None,
            detail_references=(reference,),
            occurred_at=self._clock(),
            correlation_id=correlation_id,
            event_id=f"evt_{uuid4().hex}",
            producer="project-atlas-api",
            producer_version=__version__,
        )
