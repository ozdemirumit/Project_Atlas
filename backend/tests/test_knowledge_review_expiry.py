from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.knowledge.adapters.review_expiry_memory import (
    InMemoryKnowledgeReviewRepository,
)
from atlas.modules.knowledge.application.review_expiry import (
    KnowledgeReviewError,
    KnowledgeReviewService,
)
from atlas.modules.knowledge.domain.review_expiry import (
    OwnerAbsenceResolutionKind,
    ProductEndOfSupport,
    a_review_renewal_is_recorded_without_an_evidence_reference,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, delta: timedelta) -> None:
        self.moment += delta


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service(
    clock: MutableClock | None = None,
) -> tuple[KnowledgeReviewService, CollectingAuditSink, MutableClock]:
    resolved_clock = clock or MutableClock(NOW)
    audit_sink = CollectingAuditSink()
    service = KnowledgeReviewService(
        repository=InMemoryKnowledgeReviewRepository(),
        audit_sink=audit_sink,
        clock=resolved_clock,
    )
    return service, audit_sink, resolved_clock


def test_absolute_rule_is_false() -> None:
    assert a_review_renewal_is_recorded_without_an_evidence_reference() is False


def test_product_end_of_support_expires_guidance() -> None:
    end_of_support = ProductEndOfSupport(
        product="hitachi-ops-center", version="10.9", end_of_support_at=NOW
    )
    assert end_of_support.expires_guidance_at(NOW) is True
    assert end_of_support.expires_guidance_at(NOW - timedelta(days=1)) is False


@pytest.mark.asyncio
async def test_schedule_review_and_overdue_detection() -> None:
    service, audit_sink, clock = _service()
    await service.schedule_review(
        item_id="knowledge-item.runbook.storage-failover",
        item_version="3",
        owner="subject.owner.primary",
        review_interval_days=30,
        correlation_id="correlation.test",
    )
    assert any(item.result_code == "knowledge_review_scheduled" for item in audit_sink.records)
    assert await service.is_overdue("knowledge-item.runbook.storage-failover") is False
    clock.advance(timedelta(days=31))
    assert await service.is_overdue("knowledge-item.runbook.storage-failover") is True


@pytest.mark.asyncio
async def test_is_overdue_is_false_for_an_item_with_no_schedule() -> None:
    service, _audit, _clock = _service()
    assert await service.is_overdue("knowledge-item.unscheduled") is False


@pytest.mark.asyncio
async def test_renew_requires_an_existing_schedule() -> None:
    service, _audit, _clock = _service()
    with pytest.raises(KnowledgeReviewError, match="knowledge_review_unavailable"):
        await service.renew(
            item_id="knowledge-item.unscheduled",
            renewed_by="subject.owner.primary",
            evidence_reference="review.session.2026-09-07",
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_renew_resets_the_review_window() -> None:
    service, audit_sink, clock = _service()
    await service.schedule_review(
        item_id="knowledge-item.runbook.storage-failover",
        item_version="3",
        owner="subject.owner.primary",
        review_interval_days=30,
        correlation_id="correlation.test",
    )
    clock.advance(timedelta(days=31))
    assert await service.is_overdue("knowledge-item.runbook.storage-failover") is True
    await service.renew(
        item_id="knowledge-item.runbook.storage-failover",
        renewed_by="subject.owner.primary",
        evidence_reference="review.session.2026-10-08",
        correlation_id="correlation.test",
    )
    assert any(item.result_code == "knowledge_review_renewed" for item in audit_sink.records)
    assert await service.is_overdue("knowledge-item.runbook.storage-failover") is False


@pytest.mark.asyncio
async def test_resolve_owner_absence_reassigns_the_owner() -> None:
    service, audit_sink, _clock = _service()
    await service.schedule_review(
        item_id="knowledge-item.runbook.storage-failover",
        item_version="3",
        owner="subject.owner.primary",
        review_interval_days=30,
        correlation_id="correlation.test",
    )
    resolution = await service.resolve_owner_absence(
        item_id="knowledge-item.runbook.storage-failover",
        resolution=OwnerAbsenceResolutionKind.REASSIGNED,
        new_owner="subject.owner.secondary",
        resolved_by="subject.manager.primary",
        rationale="Prior owner left the team; reassigning to the on-call storage lead.",
        correlation_id="correlation.test",
    )
    assert resolution.new_owner == "subject.owner.secondary"
    assert any(
        item.result_code == "knowledge_review_owner_absence_resolved" for item in audit_sink.records
    )


@pytest.mark.asyncio
async def test_resolve_owner_absence_suspension_requires_no_new_owner() -> None:
    service, _audit, _clock = _service()
    await service.schedule_review(
        item_id="knowledge-item.runbook.storage-failover",
        item_version="3",
        owner="subject.owner.primary",
        review_interval_days=30,
        correlation_id="correlation.test",
    )
    with pytest.raises(KnowledgeReviewError, match="knowledge_review_owner_absence_invalid"):
        await service.resolve_owner_absence(
            item_id="knowledge-item.runbook.storage-failover",
            resolution=OwnerAbsenceResolutionKind.SUSPENDED,
            new_owner="subject.owner.secondary",
            resolved_by="subject.manager.primary",
            rationale="No successor identified; suspending pending reassignment.",
            correlation_id="correlation.test",
        )
