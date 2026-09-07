"""ATLAS-027 SS22: Feedback application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.knowledge.application.feedback_ports import KnowledgeFeedbackRepository
from atlas.modules.knowledge.domain.feedback import (
    FeedbackKind,
    FeedbackWorkItemState,
    KnowledgeFeedback,
)


class KnowledgeFeedbackError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class KnowledgeFeedbackService:
    def __init__(
        self,
        *,
        repository: KnowledgeFeedbackRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def submit(
        self,
        *,
        item_id: str,
        item_version: str,
        kind: FeedbackKind,
        submitted_by: str,
        description: str,
        correlation_id: str,
    ) -> KnowledgeFeedback:
        try:
            feedback = KnowledgeFeedback(
                feedback_id=f"feedback.{uuid4().hex}",
                item_id=item_id,
                item_version=item_version,
                kind=kind,
                submitted_by=submitted_by,
                submitted_at=self._clock(),
                description=description,
                state=FeedbackWorkItemState.OPEN,
            )
        except ValueError as error:
            raise KnowledgeFeedbackError("knowledge_feedback_invalid") from error
        await self._repository.create(feedback)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.knowledge.feedback.submitted",
            item_id=item_id,
            actor=submitted_by,
            result_code="knowledge_feedback_submitted",
        )
        return feedback

    async def triage(
        self, *, feedback_id: str, triaged_by: str, correlation_id: str
    ) -> KnowledgeFeedback:
        feedback = await self._require(feedback_id)
        if feedback.state is not FeedbackWorkItemState.OPEN:
            raise KnowledgeFeedbackError("knowledge_feedback_already_triaged")
        updated = replace(
            feedback,
            state=FeedbackWorkItemState.TRIAGED,
            triaged_by=triaged_by,
            triaged_at=self._clock(),
        )
        await self._repository.update(updated)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.knowledge.feedback.triaged",
            item_id=feedback.item_id,
            actor=triaged_by,
            result_code="knowledge_feedback_triaged",
        )
        return updated

    async def resolve(
        self,
        *,
        feedback_id: str,
        resolved_by: str,
        resolution_notes: str,
        dismissed: bool,
        correlation_id: str,
    ) -> KnowledgeFeedback:
        feedback = await self._require(feedback_id)
        if feedback.state is not FeedbackWorkItemState.TRIAGED:
            raise KnowledgeFeedbackError("knowledge_feedback_not_triaged")
        final_state = (
            FeedbackWorkItemState.DISMISSED if dismissed else FeedbackWorkItemState.RESOLVED
        )
        try:
            updated = replace(feedback, state=final_state, resolution_notes=resolution_notes)
        except ValueError as error:
            raise KnowledgeFeedbackError("knowledge_feedback_invalid") from error
        await self._repository.update(updated)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.knowledge.feedback.resolved",
            item_id=feedback.item_id,
            actor=resolved_by,
            result_code=(
                "knowledge_feedback_dismissed" if dismissed else "knowledge_feedback_resolved"
            ),
        )
        return updated

    async def _require(self, feedback_id: str) -> KnowledgeFeedback:
        feedback = await self._repository.get(feedback_id)
        if feedback is None:
            raise KnowledgeFeedbackError("knowledge_feedback_unavailable")
        return feedback

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
                resource_type="resource.knowledge.feedback",
                scope_reference=item_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
            )
        )
