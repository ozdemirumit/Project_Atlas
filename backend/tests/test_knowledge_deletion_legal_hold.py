from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.knowledge.adapters.deletion_legal_hold_memory import (
    InMemoryKnowledgeDeletionRepository,
)
from atlas.modules.knowledge.application.deletion_legal_hold import (
    KnowledgeDeletionError,
    KnowledgeDeletionService,
)
from atlas.modules.knowledge.domain.deletion_legal_hold import (
    DeletionRequestState,
    a_completed_deletion_leaves_derived_chunks_embeddings_or_caches_behind,
    a_deletion_completes_while_an_active_legal_hold_exists,
    a_knowledge_tombstone_retains_the_deleted_item_s_content,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service() -> tuple[KnowledgeDeletionService, CollectingAuditSink]:
    audit_sink = CollectingAuditSink()
    service = KnowledgeDeletionService(
        repository=InMemoryKnowledgeDeletionRepository(),
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )
    return service, audit_sink


def test_absolute_rules_are_false() -> None:
    assert a_deletion_completes_while_an_active_legal_hold_exists() is False
    assert a_completed_deletion_leaves_derived_chunks_embeddings_or_caches_behind() is False
    assert a_knowledge_tombstone_retains_the_deleted_item_s_content() is False


@pytest.mark.asyncio
async def test_deletion_without_a_hold_completes() -> None:
    service, audit_sink = _service()
    request = await service.request_deletion(
        request_id="deletion.request.primary",
        item_id="knowledge-item.runbook.storage-failover",
        requested_by="subject.owner.primary",
        retention_policy_reference="retention.policy.knowledge-standard",
        correlation_id="correlation.test",
    )
    assert request.state is DeletionRequestState.REQUESTED
    completed = await service.complete_deletion(
        request_id=request.request_id,
        tombstone_id="tombstone.primary",
        deleted_by="subject.owner.primary",
        reason_code="retention_expired",
        correlation_id="correlation.test",
    )
    assert completed.state is DeletionRequestState.COMPLETED
    assert completed.derived_artifacts_removed is True
    assert completed.tombstone_id == "tombstone.primary"
    assert any(item.result_code == "knowledge_deletion_completed" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_deletion_request_is_blocked_when_a_legal_hold_is_active() -> None:
    service, audit_sink = _service()
    await service.place_legal_hold(
        hold_id="hold.litigation.primary",
        item_id="knowledge-item.runbook.storage-failover",
        authorized_by="subject.legal.primary",
        reason="Preservation order in pending litigation matter LIT-2026-014.",
        correlation_id="correlation.test",
    )
    request = await service.request_deletion(
        request_id="deletion.request.primary",
        item_id="knowledge-item.runbook.storage-failover",
        requested_by="subject.owner.primary",
        retention_policy_reference="retention.policy.knowledge-standard",
        correlation_id="correlation.test",
    )
    assert request.state is DeletionRequestState.BLOCKED_BY_LEGAL_HOLD
    assert any(
        item.result_code == "knowledge_deletion_blocked_by_legal_hold"
        for item in audit_sink.records
    )


@pytest.mark.asyncio
async def test_complete_deletion_refuses_while_a_hold_is_active() -> None:
    service, _audit = _service()
    request = await service.request_deletion(
        request_id="deletion.request.primary",
        item_id="knowledge-item.runbook.storage-failover",
        requested_by="subject.owner.primary",
        retention_policy_reference="retention.policy.knowledge-standard",
        correlation_id="correlation.test",
    )
    await service.place_legal_hold(
        hold_id="hold.litigation.primary",
        item_id="knowledge-item.runbook.storage-failover",
        authorized_by="subject.legal.primary",
        reason="Preservation order in pending litigation matter LIT-2026-014.",
        correlation_id="correlation.test",
    )
    with pytest.raises(KnowledgeDeletionError, match="knowledge_deletion_blocked_by_legal_hold"):
        await service.complete_deletion(
            request_id=request.request_id,
            tombstone_id="tombstone.primary",
            deleted_by="subject.owner.primary",
            reason_code="retention_expired",
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_completing_deletion_again_is_refused() -> None:
    service, _audit = _service()
    request = await service.request_deletion(
        request_id="deletion.request.primary",
        item_id="knowledge-item.runbook.storage-failover",
        requested_by="subject.owner.primary",
        retention_policy_reference="retention.policy.knowledge-standard",
        correlation_id="correlation.test",
    )
    await service.complete_deletion(
        request_id=request.request_id,
        tombstone_id="tombstone.primary",
        deleted_by="subject.owner.primary",
        reason_code="retention_expired",
        correlation_id="correlation.test",
    )
    with pytest.raises(KnowledgeDeletionError, match="knowledge_deletion_already_completed"):
        await service.complete_deletion(
            request_id=request.request_id,
            tombstone_id="tombstone.duplicate",
            deleted_by="subject.owner.primary",
            reason_code="retention_expired",
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_release_legal_hold_then_deletion_can_complete() -> None:
    service, audit_sink = _service()
    hold = await service.place_legal_hold(
        hold_id="hold.litigation.primary",
        item_id="knowledge-item.runbook.storage-failover",
        authorized_by="subject.legal.primary",
        reason="Preservation order in pending litigation matter LIT-2026-014.",
        correlation_id="correlation.test",
    )
    request = await service.request_deletion(
        request_id="deletion.request.primary",
        item_id="knowledge-item.runbook.storage-failover",
        requested_by="subject.owner.primary",
        retention_policy_reference="retention.policy.knowledge-standard",
        correlation_id="correlation.test",
    )
    assert request.state is DeletionRequestState.BLOCKED_BY_LEGAL_HOLD
    released = await service.release_legal_hold(
        hold_id=hold.hold_id, released_by="subject.legal.primary", correlation_id="correlation.test"
    )
    assert released.is_active_at(NOW) is False
    assert any(item.result_code == "knowledge_legal_hold_released" for item in audit_sink.records)
    completed = await service.complete_deletion(
        request_id=request.request_id,
        tombstone_id="tombstone.primary",
        deleted_by="subject.owner.primary",
        reason_code="retention_expired",
        correlation_id="correlation.test",
    )
    assert completed.state is DeletionRequestState.COMPLETED


@pytest.mark.asyncio
async def test_releasing_an_already_released_hold_is_refused() -> None:
    service, _audit = _service()
    hold = await service.place_legal_hold(
        hold_id="hold.litigation.primary",
        item_id="knowledge-item.runbook.storage-failover",
        authorized_by="subject.legal.primary",
        reason="Preservation order in pending litigation matter LIT-2026-014.",
        correlation_id="correlation.test",
    )
    await service.release_legal_hold(
        hold_id=hold.hold_id, released_by="subject.legal.primary", correlation_id="correlation.test"
    )
    with pytest.raises(KnowledgeDeletionError, match="knowledge_legal_hold_already_released"):
        await service.release_legal_hold(
            hold_id=hold.hold_id,
            released_by="subject.legal.primary",
            correlation_id="correlation.test",
        )
