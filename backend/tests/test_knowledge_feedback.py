from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.knowledge.adapters.feedback_memory import InMemoryKnowledgeFeedbackRepository
from atlas.modules.knowledge.application.feedback import (
    KnowledgeFeedbackError,
    KnowledgeFeedbackService,
)
from atlas.modules.knowledge.domain.feedback import (
    FeedbackKind,
    FeedbackWorkItemState,
    submitting_knowledge_feedback_directly_modifies_item_rank_approval_or_content,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service() -> tuple[KnowledgeFeedbackService, CollectingAuditSink]:
    audit_sink = CollectingAuditSink()
    service = KnowledgeFeedbackService(
        repository=InMemoryKnowledgeFeedbackRepository(),
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )
    return service, audit_sink


def test_absolute_rule_is_false() -> None:
    assert submitting_knowledge_feedback_directly_modifies_item_rank_approval_or_content() is False


@pytest.mark.asyncio
async def test_submit_creates_an_open_work_item() -> None:
    service, audit_sink = _service()
    feedback = await service.submit(
        item_id="knowledge-item.runbook.storage-failover",
        item_version="3",
        kind=FeedbackKind.INCORRECT_OR_OUTDATED,
        submitted_by="subject.consumer.primary",
        description="Step 4 references a decommissioned array model.",
        correlation_id="correlation.test",
    )
    assert feedback.state is FeedbackWorkItemState.OPEN
    assert any(item.result_code == "knowledge_feedback_submitted" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_triage_then_resolve_workflow() -> None:
    service, audit_sink = _service()
    feedback = await service.submit(
        item_id="knowledge-item.runbook.storage-failover",
        item_version="3",
        kind=FeedbackKind.MISSING_EVIDENCE,
        submitted_by="subject.consumer.primary",
        description="No citation for the claimed failover duration.",
        correlation_id="correlation.test",
    )
    triaged = await service.triage(
        feedback_id=feedback.feedback_id,
        triaged_by="subject.owner.primary",
        correlation_id="correlation.test",
    )
    assert triaged.state is FeedbackWorkItemState.TRIAGED
    resolved = await service.resolve(
        feedback_id=feedback.feedback_id,
        resolved_by="subject.owner.primary",
        resolution_notes="Added a citation to the vendor runbook.",
        dismissed=False,
        correlation_id="correlation.test",
    )
    assert resolved.state is FeedbackWorkItemState.RESOLVED
    assert any(item.result_code == "knowledge_feedback_resolved" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_resolve_requires_prior_triage() -> None:
    service, _audit = _service()
    feedback = await service.submit(
        item_id="knowledge-item.runbook.storage-failover",
        item_version="3",
        kind=FeedbackKind.ACCESS_CONCERN,
        submitted_by="subject.consumer.primary",
        description="This item appears visible outside its intended audience.",
        correlation_id="correlation.test",
    )
    with pytest.raises(KnowledgeFeedbackError, match="knowledge_feedback_not_triaged"):
        await service.resolve(
            feedback_id=feedback.feedback_id,
            resolved_by="subject.owner.primary",
            resolution_notes="Reviewed.",
            dismissed=False,
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_triage_cannot_be_repeated() -> None:
    service, _audit = _service()
    feedback = await service.submit(
        item_id="knowledge-item.runbook.storage-failover",
        item_version="3",
        kind=FeedbackKind.UNSAFE_OR_AMBIGUOUS_PROCEDURE,
        submitted_by="subject.consumer.primary",
        description="Step 2 does not specify a stop condition.",
        correlation_id="correlation.test",
    )
    await service.triage(
        feedback_id=feedback.feedback_id,
        triaged_by="subject.owner.primary",
        correlation_id="correlation.test",
    )
    with pytest.raises(KnowledgeFeedbackError, match="knowledge_feedback_already_triaged"):
        await service.triage(
            feedback_id=feedback.feedback_id,
            triaged_by="subject.owner.primary",
            correlation_id="correlation.test",
        )
