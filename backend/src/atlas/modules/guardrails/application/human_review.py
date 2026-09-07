"""ATLAS-047 SS28: Human Review application service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditSink
from atlas.modules.guardrails.application.audit import (
    GuardrailAuditEventKind,
    record_guardrail_event,
)
from atlas.modules.guardrails.application.human_review_ports import GuardrailReviewRepository
from atlas.modules.guardrails.domain.human_review import (
    HumanReviewQueueEntry,
    HumanReviewResolution,
    ReviewerDecision,
)
from atlas.modules.guardrails.domain.models import GuardrailClass


class GuardrailReviewError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class GuardrailReviewService:
    def __init__(
        self,
        *,
        repository: GuardrailReviewRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def enqueue(
        self, entry: HumanReviewQueueEntry, *, correlation_id: str
    ) -> HumanReviewQueueEntry:
        await self._repository.save_entry(entry)
        await self._audit(
            correlation_id=correlation_id,
            reference=entry.entry_id,
            outcome="queued",
        )
        return entry

    async def resolve(
        self,
        *,
        entry_id: str,
        decision: ReviewerDecision,
        reviewed_by: str,
        rationale: str,
        triggering_guardrail_class: GuardrailClass,
        correlation_id: str,
    ) -> HumanReviewResolution:
        entry = await self._repository.get_entry(entry_id)
        if entry is None:
            raise GuardrailReviewError("guardrail_review_entry_unavailable")
        if await self._repository.get_resolution(entry_id) is not None:
            raise GuardrailReviewError("guardrail_review_already_resolved")
        if decision not in entry.allowed_decisions:
            raise GuardrailReviewError("guardrail_review_decision_not_allowed")
        if (
            decision is ReviewerDecision.OVERTURN
            and triggering_guardrail_class is GuardrailClass.INVARIANT
        ):
            raise GuardrailReviewError("guardrail_review_invariant_cannot_be_overturned")
        try:
            resolution = HumanReviewResolution(
                entry_id=entry_id,
                decision=decision,
                reviewed_by=reviewed_by,
                reviewed_at=self._clock(),
                rationale=rationale,
            )
        except ValueError as error:
            raise GuardrailReviewError("guardrail_review_resolution_invalid") from error
        await self._repository.save_resolution(resolution)
        await self._audit(
            correlation_id=correlation_id,
            reference=entry_id,
            outcome=decision.value,
            actor_identity=reviewed_by,
        )
        return resolution

    async def _audit(
        self,
        *,
        correlation_id: str,
        reference: str,
        outcome: str,
        actor_identity: str | None = None,
    ) -> None:
        await record_guardrail_event(
            self._audit_sink,
            event_kind=GuardrailAuditEventKind.HUMAN_REVIEW,
            rule_or_incident_reference=reference,
            actor_identity=actor_identity,
            is_automation=actor_identity is None,
            outcome=outcome,
            detail_references=(reference,),
            occurred_at=self._clock(),
            correlation_id=correlation_id,
            event_id=f"evt_{uuid4().hex}",
            producer="project-atlas-api",
            producer_version=__version__,
        )
