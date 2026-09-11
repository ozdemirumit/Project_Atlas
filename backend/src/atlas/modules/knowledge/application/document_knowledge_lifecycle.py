"""Makes docs/027_Knowledge_Engine.md SS8/SS21 reachable for the real document-sourced knowledge
pipeline. See ``atlas.modules.knowledge.domain.document_knowledge_lifecycle`` for why this targets
that pipeline (``document_knowledge.py``/``document_retrieval.py``) and not the older, still-
synthetic Operational-chain ``KnowledgeLifecycle`` enum.

Real state-machine enforcement, mirroring ``operations/application/service.py``'s
``OperationResourceService`` shape (a mutable "current state" row read-checked-then-compare-and-
swap-written, not an append-only chain): ``suspend`` only from ``ACTIVE``, ``resume`` only from
``SUSPENDED``, ``supersede`` only from ``ACTIVE`` (and only to a replacement whose own current
state already resolves to ``ACTIVE``), ``retire`` only from ``SUPERSEDED``. Every wrong-state
attempt raises a real ``DocumentKnowledgeError`` the route layer maps to a real `409` -- never a
silent no-op.

Known, deliberate scope limit on ``supersede``'s replacement check: this service verifies the
*replacement item's own lifecycle state* resolves to ``ACTIVE`` via this module's own repository,
but it does NOT verify the replacement id exists as a real ``DocumentKnowledgeDraft`` in
``document_knowledge.py``'s repository -- that repository has no lookup by ``knowledge_item_id``
at all (only by ``draft_id``/``review_id``/``approval_id``/``preparation_id``), and
``knowledge_item_id`` is not an indexed column on ``DocumentKnowledgeDraftModel`` (it lives only
inside that table's JSONB ``payload``), so adding real existence verification would require a
schema/index change to an already-hardened, heavily-depended-on table. That is out of proportion
to this build; the lifecycle-state check is the real, proportionate substitute -- it still rejects
superseding to an item that is itself suspended, superseded, or retired, and still rejects
malformed ids (the domain dataclass's ``validate_stable_identifier`` call) and self-supersession.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.application.document_knowledge_lifecycle_ports import (
    DocumentKnowledgeError,
    DocumentKnowledgeLifecycleRepository,
    DocumentKnowledgePermissionAuthorizer,
)
from atlas.modules.knowledge.domain.document_knowledge_lifecycle import (
    DocumentKnowledgeConflict,
    DocumentKnowledgeConflictType,
    DocumentKnowledgeItemLifecycleRecord,
    DocumentKnowledgeItemLifecycleState,
    canonical_conflict_pair,
)

_KNOWLEDGE_DOCUMENT_LIFECYCLE_CREATE = "knowledge.document-lifecycle.create"
_KNOWLEDGE_DOCUMENT_LIFECYCLE_READ = "knowledge.document-lifecycle.read"
_KNOWLEDGE_DOCUMENT_CONFLICT_CREATE = "knowledge.document-conflicts.create"
_KNOWLEDGE_DOCUMENT_CONFLICT_READ = "knowledge.document-conflicts.read"

_ACTIVE = DocumentKnowledgeItemLifecycleState.ACTIVE
_SUSPENDED = DocumentKnowledgeItemLifecycleState.SUSPENDED
_SUPERSEDED = DocumentKnowledgeItemLifecycleState.SUPERSEDED
_RETIRED = DocumentKnowledgeItemLifecycleState.RETIRED


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeItemLifecycleView:
    """``get_lifecycle``'s return shape. Not the same type as
    ``DocumentKnowledgeItemLifecycleRecord`` because the overwhelming majority of items have no
    persisted record at all -- SS8's "Published" default -- and there is no real record to hand
    back for those; this view represents that default explicitly (``reason``/``updated_by``/
    ``updated_at``/``superseded_by_item_id`` are all ``None``) rather than fabricating one.
    """

    knowledge_item_id: str
    organization_id: str
    environment_id: str
    state: DocumentKnowledgeItemLifecycleState
    reason: str | None
    superseded_by_item_id: str | None
    updated_by: str | None
    updated_at: datetime | None


class DocumentKnowledgeLifecycleService:
    def __init__(
        self,
        *,
        repository: DocumentKnowledgeLifecycleRepository,
        permission_authorizer: DocumentKnowledgePermissionAuthorizer,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._permission_authorizer = permission_authorizer
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise DocumentKnowledgeError(
                "document_knowledge_human_required", "Only a human actor may perform this action."
            )

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        scope_reference: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.document-item-lifecycle",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.knowledge.document-item-lifecycle",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    async def _current_state(
        self, *, knowledge_item_id: str, organization_id: str, environment_id: str
    ) -> tuple[DocumentKnowledgeItemLifecycleRecord | None, DocumentKnowledgeItemLifecycleState]:
        record = await self._repository.get_lifecycle(
            knowledge_item_id=knowledge_item_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        return record, (record.state if record is not None else _ACTIVE)

    async def _transition(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        knowledge_item_id: str,
        reason: str,
        correlation_id: str,
        required_current_states: frozenset[DocumentKnowledgeItemLifecycleState],
        new_state: DocumentKnowledgeItemLifecycleState,
        superseded_by_item_id: str | None,
        result_code: str,
    ) -> DocumentKnowledgeItemLifecycleRecord:
        self._require_human(actor)
        if not reason.strip():
            raise DocumentKnowledgeError(
                "document_knowledge_lifecycle_reason_invalid",
                "A real, non-empty reason is required for every lifecycle transition.",
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_KNOWLEDGE_DOCUMENT_LIFECYCLE_CREATE,
            correlation_id=correlation_id,
        )
        current, current_state = await self._current_state(
            knowledge_item_id=knowledge_item_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if current_state not in required_current_states:
            raise DocumentKnowledgeError(
                "document_knowledge_lifecycle_transition_not_allowed",
                f"Cannot move a {current_state.value} item to {new_state.value}.",
            )
        now = self._clock()
        try:
            replacement = DocumentKnowledgeItemLifecycleRecord(
                knowledge_item_id=knowledge_item_id,
                organization_id=organization_id,
                environment_id=environment_id,
                state=new_state,
                reason=reason.strip(),
                updated_by=actor.subject_id,
                updated_at=now,
                created_at=current.created_at if current is not None else now,
                superseded_by_item_id=superseded_by_item_id,
            )
        except ValueError as error:
            raise DocumentKnowledgeError(
                "document_knowledge_lifecycle_invalid", str(error)
            ) from error
        if not await self._repository.put_lifecycle(expected=current, replacement=replacement):
            raise DocumentKnowledgeError(
                "document_knowledge_lifecycle_transition_conflict",
                "The item's lifecycle state changed concurrently; retry against the latest state.",
            )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=_KNOWLEDGE_DOCUMENT_LIFECYCLE_CREATE,
            result_code=result_code,
            scope_reference=knowledge_item_id,
        )
        return replacement

    async def suspend(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        knowledge_item_id: str,
        reason: str,
        correlation_id: str,
    ) -> DocumentKnowledgeItemLifecycleRecord:
        return await self._transition(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            knowledge_item_id=knowledge_item_id,
            reason=reason,
            correlation_id=correlation_id,
            required_current_states=frozenset({_ACTIVE}),
            new_state=_SUSPENDED,
            superseded_by_item_id=None,
            result_code="document_knowledge_item_suspended",
        )

    async def resume(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        knowledge_item_id: str,
        reason: str,
        correlation_id: str,
    ) -> DocumentKnowledgeItemLifecycleRecord:
        return await self._transition(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            knowledge_item_id=knowledge_item_id,
            reason=reason,
            correlation_id=correlation_id,
            required_current_states=frozenset({_SUSPENDED}),
            new_state=_ACTIVE,
            superseded_by_item_id=None,
            result_code="document_knowledge_item_resumed",
        )

    async def supersede(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        knowledge_item_id: str,
        superseded_by_item_id: str,
        reason: str,
        correlation_id: str,
    ) -> DocumentKnowledgeItemLifecycleRecord:
        if superseded_by_item_id == knowledge_item_id:
            raise DocumentKnowledgeError(
                "document_knowledge_lifecycle_supersession_target_invalid",
                "An item cannot be superseded by itself.",
            )
        # See the module docstring: this confirms the replacement's own lifecycle state
        # resolves to ACTIVE -- the real, proportionate substitute for full existence
        # verification against the document-knowledge draft repository.
        _, replacement_state = await self._current_state(
            knowledge_item_id=superseded_by_item_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if replacement_state is not _ACTIVE:
            raise DocumentKnowledgeError(
                "document_knowledge_lifecycle_supersession_target_invalid",
                "The superseding item must itself be currently active.",
            )
        return await self._transition(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            knowledge_item_id=knowledge_item_id,
            reason=reason,
            correlation_id=correlation_id,
            required_current_states=frozenset({_ACTIVE}),
            new_state=_SUPERSEDED,
            superseded_by_item_id=superseded_by_item_id,
            result_code="document_knowledge_item_superseded",
        )

    async def retire(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        knowledge_item_id: str,
        reason: str,
        correlation_id: str,
    ) -> DocumentKnowledgeItemLifecycleRecord:
        return await self._transition(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            knowledge_item_id=knowledge_item_id,
            reason=reason,
            correlation_id=correlation_id,
            required_current_states=frozenset({_SUPERSEDED}),
            new_state=_RETIRED,
            superseded_by_item_id=None,
            result_code="document_knowledge_item_retired",
        )

    async def get_lifecycle(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        knowledge_item_id: str,
        correlation_id: str,
    ) -> DocumentKnowledgeItemLifecycleView:
        self._require_human(actor)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_KNOWLEDGE_DOCUMENT_LIFECYCLE_READ,
            correlation_id=correlation_id,
        )
        record, state = await self._current_state(
            knowledge_item_id=knowledge_item_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=_KNOWLEDGE_DOCUMENT_LIFECYCLE_READ,
            result_code="document_knowledge_item_lifecycle_read",
            scope_reference=knowledge_item_id,
        )
        if record is None:
            return DocumentKnowledgeItemLifecycleView(
                knowledge_item_id=knowledge_item_id,
                organization_id=organization_id,
                environment_id=environment_id,
                state=state,
                reason=None,
                superseded_by_item_id=None,
                updated_by=None,
                updated_at=None,
            )
        return DocumentKnowledgeItemLifecycleView(
            knowledge_item_id=record.knowledge_item_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            state=record.state,
            reason=record.reason,
            superseded_by_item_id=record.superseded_by_item_id,
            updated_by=record.updated_by,
            updated_at=record.updated_at,
        )

    async def record_conflict(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        knowledge_item_id_a: str,
        knowledge_item_id_b: str,
        conflict_type: DocumentKnowledgeConflictType,
        correlation_id: str,
    ) -> DocumentKnowledgeConflict:
        self._require_human(actor)
        if knowledge_item_id_a == knowledge_item_id_b:
            raise DocumentKnowledgeError(
                "document_knowledge_conflict_target_invalid",
                "A conflict requires two distinct knowledge items.",
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_KNOWLEDGE_DOCUMENT_CONFLICT_CREATE,
            correlation_id=correlation_id,
        )
        item_a, item_b = canonical_conflict_pair(knowledge_item_id_a, knowledge_item_id_b)
        now = self._clock()
        seed = sha256(
            f"{organization_id}:{environment_id}:{item_a}:{item_b}:{conflict_type.value}:"
            f"{now.isoformat()}:{uuid4().hex}".encode()
        ).hexdigest()
        try:
            conflict = DocumentKnowledgeConflict(
                conflict_id=f"document-knowledge-conflict.{seed[:24]}",
                organization_id=organization_id,
                environment_id=environment_id,
                knowledge_item_id_a=item_a,
                knowledge_item_id_b=item_b,
                conflict_type=conflict_type,
                detected_by=actor.subject_id,
                detected_at=now,
            )
        except ValueError as error:
            raise DocumentKnowledgeError(
                "document_knowledge_conflict_target_invalid", str(error)
            ) from error
        if not await self._repository.add_conflict(conflict):
            raise DocumentKnowledgeError(
                "document_knowledge_conflict_persistence_uncertain",
                "The conflict record could not be confirmed persisted.",
            )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=_KNOWLEDGE_DOCUMENT_CONFLICT_CREATE,
            result_code="document_knowledge_conflict_recorded",
            scope_reference=conflict.conflict_id,
        )
        return conflict

    async def resolve_conflict(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        conflict_id: str,
        resolution: str,
        correlation_id: str,
    ) -> DocumentKnowledgeConflict:
        self._require_human(actor)
        if not resolution.strip():
            raise DocumentKnowledgeError(
                "document_knowledge_conflict_resolution_invalid",
                "A real, non-empty resolution is required.",
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_KNOWLEDGE_DOCUMENT_CONFLICT_CREATE,
            correlation_id=correlation_id,
        )
        existing = await self._repository.get_conflict(
            conflict_id=conflict_id, organization_id=organization_id, environment_id=environment_id
        )
        if existing is None:
            raise DocumentKnowledgeError(
                "document_knowledge_conflict_not_found", "The referenced conflict does not exist."
            )
        if existing.is_resolved:
            raise DocumentKnowledgeError(
                "document_knowledge_conflict_already_resolved",
                "This conflict has already been resolved.",
            )
        now = self._clock()
        updated = replace(
            existing,
            resolution=resolution.strip(),
            resolved_by=actor.subject_id,
            resolved_at=now,
        )
        if not await self._repository.update_conflict(expected=existing, replacement=updated):
            raise DocumentKnowledgeError(
                "document_knowledge_conflict_transition_conflict",
                "The conflict record changed concurrently; retry against the latest state.",
            )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=_KNOWLEDGE_DOCUMENT_CONFLICT_CREATE,
            result_code="document_knowledge_conflict_resolved",
            scope_reference=conflict_id,
        )
        return updated

    async def list_conflicts(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        knowledge_item_id: str,
        correlation_id: str,
    ) -> tuple[DocumentKnowledgeConflict, ...]:
        self._require_human(actor)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_KNOWLEDGE_DOCUMENT_CONFLICT_READ,
            correlation_id=correlation_id,
        )
        conflicts = await self._repository.list_conflicts_for_item(
            knowledge_item_id=knowledge_item_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=_KNOWLEDGE_DOCUMENT_CONFLICT_READ,
            result_code="document_knowledge_conflicts_listed",
            scope_reference=knowledge_item_id,
        )
        return conflicts

    async def close(self) -> None:
        await self._repository.close()


__all__ = ["DocumentKnowledgeItemLifecycleView", "DocumentKnowledgeLifecycleService"]
