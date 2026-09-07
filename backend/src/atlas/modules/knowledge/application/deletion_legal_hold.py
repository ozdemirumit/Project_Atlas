"""ATLAS-027 SS24: Deletion and Legal Hold application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.knowledge.application.deletion_legal_hold_ports import (
    KnowledgeDeletionRepository,
)
from atlas.modules.knowledge.domain.deletion_legal_hold import (
    DeletionRequest,
    DeletionRequestState,
    KnowledgeTombstone,
    LegalHold,
)


class KnowledgeDeletionError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class KnowledgeDeletionService:
    def __init__(
        self,
        *,
        repository: KnowledgeDeletionRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def place_legal_hold(
        self, *, hold_id: str, item_id: str, authorized_by: str, reason: str, correlation_id: str
    ) -> LegalHold:
        try:
            hold = LegalHold(
                hold_id=hold_id,
                item_id=item_id,
                authorized_by=authorized_by,
                reason=reason,
                placed_at=self._clock(),
            )
        except ValueError as error:
            raise KnowledgeDeletionError("knowledge_legal_hold_invalid") from error
        await self._repository.save_hold(hold)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.knowledge.legal-hold.placed",
            item_id=item_id,
            actor=authorized_by,
            result_code="knowledge_legal_hold_placed",
        )
        return hold

    async def release_legal_hold(
        self, *, hold_id: str, released_by: str, correlation_id: str
    ) -> LegalHold:
        hold = await self._repository.get_hold(hold_id)
        if hold is None:
            raise KnowledgeDeletionError("knowledge_legal_hold_unavailable")
        if not hold.is_active_at(self._clock()):
            raise KnowledgeDeletionError("knowledge_legal_hold_already_released")
        updated = replace(hold, released_at=self._clock(), release_authorized_by=released_by)
        await self._repository.save_hold(updated)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.knowledge.legal-hold.released",
            item_id=hold.item_id,
            actor=released_by,
            result_code="knowledge_legal_hold_released",
        )
        return updated

    async def request_deletion(
        self,
        *,
        request_id: str,
        item_id: str,
        requested_by: str,
        retention_policy_reference: str,
        correlation_id: str,
    ) -> DeletionRequest:
        active_holds = await self._repository.active_holds_for_item(item_id)
        state = (
            DeletionRequestState.BLOCKED_BY_LEGAL_HOLD
            if active_holds
            else DeletionRequestState.REQUESTED
        )
        try:
            request = DeletionRequest(
                request_id=request_id,
                item_id=item_id,
                requested_by=requested_by,
                requested_at=self._clock(),
                retention_policy_reference=retention_policy_reference,
                state=state,
            )
        except ValueError as error:
            raise KnowledgeDeletionError("knowledge_deletion_request_invalid") from error
        await self._repository.save_request(request)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.knowledge.deletion.requested",
            item_id=item_id,
            actor=requested_by,
            result_code=(
                "knowledge_deletion_blocked_by_legal_hold"
                if active_holds
                else "knowledge_deletion_requested"
            ),
        )
        return request

    async def complete_deletion(
        self,
        *,
        request_id: str,
        tombstone_id: str,
        deleted_by: str,
        reason_code: str,
        correlation_id: str,
    ) -> DeletionRequest:
        request = await self._repository.get_request(request_id)
        if request is None:
            raise KnowledgeDeletionError("knowledge_deletion_request_unavailable")
        if request.state is DeletionRequestState.COMPLETED:
            raise KnowledgeDeletionError("knowledge_deletion_already_completed")
        active_holds = await self._repository.active_holds_for_item(request.item_id)
        if active_holds:
            blocked = replace(request, state=DeletionRequestState.BLOCKED_BY_LEGAL_HOLD)
            await self._repository.save_request(blocked)
            await self._audit(
                correlation_id=correlation_id,
                event_type="atlas.knowledge.deletion.blocked",
                item_id=request.item_id,
                actor=deleted_by,
                result_code="knowledge_deletion_blocked_by_legal_hold",
            )
            raise KnowledgeDeletionError("knowledge_deletion_blocked_by_legal_hold")
        now = self._clock()
        try:
            tombstone = KnowledgeTombstone(
                tombstone_id=tombstone_id,
                item_id=request.item_id,
                deletion_request_id=request.request_id,
                deleted_at=now,
                deleted_by=deleted_by,
                reason_code=reason_code,
            )
            completed = replace(
                request,
                state=DeletionRequestState.COMPLETED,
                completed_at=now,
                derived_artifacts_removed=True,
                tombstone_id=tombstone.tombstone_id,
            )
        except ValueError as error:
            raise KnowledgeDeletionError("knowledge_deletion_completion_invalid") from error
        await self._repository.save_tombstone(tombstone)
        await self._repository.save_request(completed)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.knowledge.deletion.completed",
            item_id=request.item_id,
            actor=deleted_by,
            result_code="knowledge_deletion_completed",
        )
        return completed

    async def _audit(
        self, *, correlation_id: str, event_type: str, item_id: str, actor: str, result_code: str
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor,
                actor_type=None,
                authentication_method=None,
                assurance_level=None,
                permission_id=None,
                resource_type="resource.knowledge.deletion",
                scope_reference=item_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
            )
        )
