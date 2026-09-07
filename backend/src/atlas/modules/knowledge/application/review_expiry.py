"""ATLAS-027 SS23: Review and Expiry application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.knowledge.application.review_expiry_ports import KnowledgeReviewRepository
from atlas.modules.knowledge.domain.review_expiry import (
    OwnerAbsenceResolution,
    OwnerAbsenceResolutionKind,
    ReviewDueRecord,
    ReviewRenewal,
)


class KnowledgeReviewError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class KnowledgeReviewService:
    def __init__(
        self,
        *,
        repository: KnowledgeReviewRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def schedule_review(
        self,
        *,
        item_id: str,
        item_version: str,
        owner: str,
        review_interval_days: int,
        correlation_id: str,
    ) -> ReviewDueRecord:
        now = self._clock()
        try:
            record = ReviewDueRecord(
                item_id=item_id,
                item_version=item_version,
                owner=owner,
                review_interval_days=review_interval_days,
                last_reviewed_at=now,
                next_review_due_at=now + timedelta(days=review_interval_days),
            )
        except ValueError as error:
            raise KnowledgeReviewError("knowledge_review_invalid") from error
        await self._repository.save_due(record)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.knowledge.review.scheduled",
            item_id=item_id,
            actor=owner,
            result_code="knowledge_review_scheduled",
        )
        return record

    async def renew(
        self,
        *,
        item_id: str,
        renewed_by: str,
        evidence_reference: str,
        correlation_id: str,
    ) -> ReviewRenewal:
        current = await self._repository.get_due(item_id)
        if current is None:
            raise KnowledgeReviewError("knowledge_review_unavailable")
        now = self._clock()
        try:
            renewal = ReviewRenewal(
                item_id=item_id,
                item_version=current.item_version,
                renewed_by=renewed_by,
                renewed_at=now,
                evidence_reference=evidence_reference,
                next_review_due_at=now + timedelta(days=current.review_interval_days),
            )
        except ValueError as error:
            raise KnowledgeReviewError("knowledge_review_renewal_invalid") from error
        await self._repository.save_renewal(renewal)
        await self._repository.save_due(
            replace(current, last_reviewed_at=now, next_review_due_at=renewal.next_review_due_at)
        )
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.knowledge.review.renewed",
            item_id=item_id,
            actor=renewed_by,
            result_code="knowledge_review_renewed",
        )
        return renewal

    async def resolve_owner_absence(
        self,
        *,
        item_id: str,
        resolution: OwnerAbsenceResolutionKind,
        new_owner: str | None,
        resolved_by: str,
        rationale: str,
        correlation_id: str,
    ) -> OwnerAbsenceResolution:
        current = await self._repository.get_due(item_id)
        if current is None:
            raise KnowledgeReviewError("knowledge_review_unavailable")
        try:
            record = OwnerAbsenceResolution(
                item_id=item_id,
                prior_owner=current.owner,
                resolution=resolution,
                new_owner=new_owner,
                resolved_by=resolved_by,
                resolved_at=self._clock(),
                rationale=rationale,
            )
        except ValueError as error:
            raise KnowledgeReviewError("knowledge_review_owner_absence_invalid") from error
        await self._repository.save_owner_absence_resolution(record)
        if resolution is OwnerAbsenceResolutionKind.REASSIGNED and new_owner is not None:
            await self._repository.save_due(replace(current, owner=new_owner))
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.knowledge.review.owner-absence-resolved",
            item_id=item_id,
            actor=resolved_by,
            result_code="knowledge_review_owner_absence_resolved",
        )
        return record

    async def is_overdue(self, item_id: str) -> bool:
        current = await self._repository.get_due(item_id)
        if current is None:
            return False
        return current.is_overdue_at(self._clock())

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
                resource_type="resource.knowledge.review",
                scope_reference=item_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
            )
        )
