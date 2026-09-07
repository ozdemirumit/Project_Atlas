from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.guardrails.adapters.human_review_memory import (
    InMemoryGuardrailReviewRepository,
)
from atlas.modules.guardrails.application.human_review import (
    GuardrailReviewError,
    GuardrailReviewService,
)
from atlas.modules.guardrails.domain.human_review import (
    DetectedElement,
    HumanReviewQueueEntry,
    ReviewerDecision,
    a_human_reviewer_overturns_an_invariant_class_deterministic_block,
)
from atlas.modules.guardrails.domain.models import GuardrailClass

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _entry(**overrides: object) -> HumanReviewQueueEntry:
    values: dict[str, object] = {
        "entry_id": "review-entry.primary",
        "triggered_rule_id": "rule.dlp.credential-pattern",
        "safe_rationale": "Output matched a credential-shaped pattern.",
        "request_reference": "request.chat.001",
        "bounded_context_reference": "context.chat.001.bounded",
        "detected_elements": (
            DetectedElement(kind="credential_pattern", description="[redacted]", redacted=True),
        ),
        "proposed_disposition": "Block and request human confirmation.",
        "proposed_impact": "Output withheld pending review.",
        "related_policy_reference": None,
        "related_approval_reference": None,
        "related_connector_reference": None,
        "related_audit_reference": "audit.evt.001",
        "allowed_decisions": (ReviewerDecision.UPHOLD, ReviewerDecision.OVERTURN),
        "created_at": NOW,
    }
    values.update(overrides)
    return HumanReviewQueueEntry(**values)  # type: ignore[arg-type]


def _service() -> tuple[GuardrailReviewService, CollectingAuditSink]:
    audit_sink = CollectingAuditSink()
    service = GuardrailReviewService(
        repository=InMemoryGuardrailReviewRepository(),
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )
    return service, audit_sink


def test_absolute_rule_is_false() -> None:
    assert a_human_reviewer_overturns_an_invariant_class_deterministic_block() is False


@pytest.mark.asyncio
async def test_enqueue_and_resolve() -> None:
    service, audit_sink = _service()
    entry = await service.enqueue(_entry(), correlation_id="correlation.test")
    resolution = await service.resolve(
        entry_id=entry.entry_id,
        decision=ReviewerDecision.UPHOLD,
        reviewed_by="subject.reviewer.primary",
        rationale="Confirmed the pattern was a real credential fragment.",
        triggering_guardrail_class=GuardrailClass.POLICY_CONFIGURABLE,
        correlation_id="correlation.test",
    )
    assert resolution.decision is ReviewerDecision.UPHOLD
    assert any(item.outcome == "queued" for item in audit_sink.records)
    assert any(item.outcome == "uphold" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_resolve_rejects_a_decision_outside_the_allowed_set() -> None:
    service, _audit = _service()
    entry = await service.enqueue(
        _entry(allowed_decisions=(ReviewerDecision.UPHOLD,)), correlation_id="correlation.test"
    )
    with pytest.raises(GuardrailReviewError, match="guardrail_review_decision_not_allowed"):
        await service.resolve(
            entry_id=entry.entry_id,
            decision=ReviewerDecision.OVERTURN,
            reviewed_by="subject.reviewer.primary",
            rationale="Attempting an overturn.",
            triggering_guardrail_class=GuardrailClass.POLICY_CONFIGURABLE,
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_resolve_refuses_overturning_an_invariant_class_decision() -> None:
    service, _audit = _service()
    entry = await service.enqueue(_entry(), correlation_id="correlation.test")
    with pytest.raises(
        GuardrailReviewError, match="guardrail_review_invariant_cannot_be_overturned"
    ):
        await service.resolve(
            entry_id=entry.entry_id,
            decision=ReviewerDecision.OVERTURN,
            reviewed_by="subject.reviewer.primary",
            rationale="Attempting to overturn an invariant block.",
            triggering_guardrail_class=GuardrailClass.INVARIANT,
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_resolve_refuses_a_second_resolution() -> None:
    service, _audit = _service()
    entry = await service.enqueue(_entry(), correlation_id="correlation.test")
    await service.resolve(
        entry_id=entry.entry_id,
        decision=ReviewerDecision.UPHOLD,
        reviewed_by="subject.reviewer.primary",
        rationale="Confirmed.",
        triggering_guardrail_class=GuardrailClass.POLICY_CONFIGURABLE,
        correlation_id="correlation.test",
    )
    with pytest.raises(GuardrailReviewError, match="guardrail_review_already_resolved"):
        await service.resolve(
            entry_id=entry.entry_id,
            decision=ReviewerDecision.UPHOLD,
            reviewed_by="subject.reviewer.primary",
            rationale="Confirmed again.",
            triggering_guardrail_class=GuardrailClass.POLICY_CONFIGURABLE,
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_resolve_requires_an_existing_entry() -> None:
    service, _audit = _service()
    with pytest.raises(GuardrailReviewError, match="guardrail_review_entry_unavailable"):
        await service.resolve(
            entry_id="review-entry.no-such-one",
            decision=ReviewerDecision.UPHOLD,
            reviewed_by="subject.reviewer.primary",
            rationale="N/A",
            triggering_guardrail_class=GuardrailClass.POLICY_CONFIGURABLE,
            correlation_id="correlation.test",
        )


def test_detected_element_must_be_redacted() -> None:
    with pytest.raises(ValueError, match="must be redacted"):
        DetectedElement(kind="credential_pattern", description="raw value shown", redacted=False)
