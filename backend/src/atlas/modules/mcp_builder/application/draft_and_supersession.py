"""ATLAS-022 SS9/SS26: Builder project draft and supersession application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.mcp_builder.application.draft_and_supersession_ports import (
    BuilderDraftRepository,
)
from atlas.modules.mcp_builder.domain.draft_and_supersession import (
    BuilderProjectDraft,
    BuilderProjectSupersession,
)


class BuilderDraftError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BuilderDraftService:
    def __init__(
        self,
        *,
        repository: BuilderDraftRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create_draft(
        self,
        *,
        draft_id: str,
        organization_id: str,
        environment_id: str,
        owner_id: str,
        vendor: str,
        product: str,
        target_environment: str,
        notes: str,
        correlation_id: str,
    ) -> BuilderProjectDraft:
        now = self._clock()
        try:
            draft = BuilderProjectDraft(
                draft_id=draft_id,
                organization_id=organization_id,
                environment_id=environment_id,
                owner_id=owner_id,
                vendor=vendor,
                product=product,
                target_environment=target_environment,
                notes=notes,
                created_at=now,
                updated_at=now,
            )
        except ValueError as error:
            raise BuilderDraftError("builder_draft_invalid") from error
        await self._repository.save_draft(draft)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.mcp-builder.draft",
            reference=draft_id,
            actor=owner_id,
            outcome="created",
        )
        return draft

    async def mark_analyzed(
        self, *, draft_id: str, analyzed_project_id: str, correlation_id: str
    ) -> BuilderProjectDraft:
        draft = await self._repository.get_draft(draft_id)
        if draft is None:
            raise BuilderDraftError("builder_draft_unavailable")
        if draft.analyzed_project_id is not None:
            raise BuilderDraftError("builder_draft_already_analyzed")
        updated = replace(draft, analyzed_project_id=analyzed_project_id, updated_at=self._clock())
        await self._repository.save_draft(updated)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.mcp-builder.draft",
            reference=draft_id,
            actor=draft.owner_id,
            outcome="analyzed",
        )
        return updated

    async def record_supersession(
        self,
        *,
        supersession_id: str,
        superseded_project_id: str,
        superseding_project_id: str,
        reason: str,
        recorded_by: str,
        correlation_id: str,
    ) -> BuilderProjectSupersession:
        if await self._repository.get_supersession_for(superseded_project_id) is not None:
            raise BuilderDraftError("builder_project_already_superseded")
        try:
            supersession = BuilderProjectSupersession(
                supersession_id=supersession_id,
                superseded_project_id=superseded_project_id,
                superseding_project_id=superseding_project_id,
                reason=reason,
                recorded_by=recorded_by,
                recorded_at=self._clock(),
            )
        except ValueError as error:
            raise BuilderDraftError("builder_project_supersession_invalid") from error
        await self._repository.save_supersession(supersession)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.mcp-builder.supersession",
            reference=superseded_project_id,
            actor=recorded_by,
            outcome="recorded",
        )
        return supersession

    async def _audit(
        self, *, correlation_id: str, event_type: str, reference: str, actor: str, outcome: str
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
                resource_type="resource.mcp-builder.project",
                scope_reference=reference,
                decision_id=None,
                outcome=outcome,
                result_code=f"{event_type}.{outcome}",
            )
        )
