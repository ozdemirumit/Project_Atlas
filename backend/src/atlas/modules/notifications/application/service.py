"""`NotificationService`: the real, RBAC-reachable read side of the notifications module. See
`atlas.modules.notifications.domain.models` for why this module exists and stops at durable,
pull-based, in-app delivery.

`create()` is the one method with no `actor`-based authorization of its own: it is only ever
called by a trusted in-process event-bus subscriber reacting to an already-committed domain event
(see `atlas.modules.notifications.application.subscriber`), never reachable over HTTP. There is no
external caller to authorize there -- the authority is the already-authorized state transition the
subscriber is reacting to, the same posture `atlas.core.audit` records are written under (no
per-write permission check of their own).

`list_for_subject`/`mark_read` are the two real HTTP-reachable methods, and both are absolute
about ownership: a notification is inherently personal, so unlike
`OperationResourceService.get()`/`cancel()` (which fall back to an elevated cross-subject
permission) there is no cross-subject read path here at all -- a caller only ever sees or marks
their own `recipient_subject_id`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.pagination import CursorCodec, CursorDecodeError
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.notifications.application.ports import NotificationError, NotificationRepository
from atlas.modules.notifications.domain.models import Notification

_RESOURCE_TYPE = "resource.notifications"

# Mirrors HumanReviewService.MAX_INBOX_SCAN -- a real, defensive upper bound on how many
# candidate rows a single list call will materialize before paginating in-process.
MAX_NOTIFICATION_SCAN = 1000


@dataclass(frozen=True, slots=True)
class NotificationPage:
    items: tuple[Notification, ...]
    next_cursor: str | None
    limit: int


class NotificationService:
    def __init__(
        self,
        *,
        repository: NotificationRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))
        self._cursor_codec = CursorCodec()

    @property
    def repository(self) -> NotificationRepository:
        return self._repository

    async def close(self) -> None:
        await self._repository.close()

    async def create(
        self,
        *,
        recipient_subject_id: str,
        organization_id: str,
        environment_id: str,
        notification_type: str,
        reference_id: str,
        summary: str,
        correlation_id: str,
        expires_at: datetime | None = None,
    ) -> Notification:
        now = self._clock()
        try:
            notification = Notification(
                notification_id=f"notification_{uuid4().hex}",
                recipient_subject_id=recipient_subject_id,
                organization_id=organization_id,
                environment_id=environment_id,
                notification_type=notification_type,
                reference_id=reference_id,
                summary=summary,
                created_at=now,
                read_at=None,
                expires_at=expires_at,
            )
        except ValueError as error:
            raise NotificationError("notification_invalid", str(error)) from error
        if not await self._repository.add(notification):
            raise NotificationError("notification_persistence_conflict")
        await self._audit(
            subject_id=recipient_subject_id,
            actor_type="service",
            authentication_method=None,
            assurance_level=None,
            correlation_id=correlation_id,
            notification_id=notification.notification_id,
            result_code="notification_created",
        )
        return notification

    async def list_for_subject(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        unread_only: bool = False,
        cursor: str | None = None,
        limit: int = 20,
        correlation_id: str,
    ) -> NotificationPage:
        if not 1 <= limit <= 100:
            raise NotificationError("notification_list_limit_invalid")
        candidates = await self._repository.list_candidates(
            recipient_subject_id=actor.subject_id,
            organization_id=organization_id,
            environment_id=environment_id,
            unread_only=unread_only,
            limit=MAX_NOTIFICATION_SCAN + 1,
        )
        if len(candidates) > MAX_NOTIFICATION_SCAN:
            raise NotificationError("notification_list_capacity_exceeded")
        ordered = sorted(candidates, key=lambda item: (item.created_at, item.notification_id))
        start = 0
        if cursor is not None:
            try:
                start = self._cursor_codec.decode(cursor)
            except CursorDecodeError as exc:
                raise NotificationError("notification_list_cursor_invalid") from exc
        page_items = tuple(ordered[start : start + limit])
        has_more = start + limit < len(ordered)
        next_cursor = (
            self._cursor_codec.encode(start + len(page_items)) if has_more and page_items else None
        )
        await self._audit(
            subject_id=actor.subject_id,
            actor_type=actor.kind.value,
            authentication_method=actor.authentication_method.value,
            assurance_level=actor.assurance_level.value,
            correlation_id=correlation_id,
            notification_id=None,
            result_code="notification_list_read",
            target_metadata=(("count", str(len(page_items))),),
        )
        return NotificationPage(items=page_items, next_cursor=next_cursor, limit=limit)

    async def mark_read(
        self,
        *,
        actor: AuthenticatedSubject,
        notification_id: str,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> Notification:
        notification = await self._repository.get(
            notification_id=notification_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if notification is None or notification.recipient_subject_id != actor.subject_id:
            # A notification belonging to someone else is indistinguishable from one that does
            # not exist at all -- the same enumeration-control posture ApprovalService's
            # _visible()/get() already takes for a foreign-scope approval.
            await self._audit(
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                correlation_id=correlation_id,
                notification_id=notification_id,
                result_code="notification_not_found",
                outcome="denied",
            )
            raise NotificationError("notification_not_found")
        if notification.is_read:
            # Idempotent: marking an already-read notification read again succeeds without
            # altering its original read_at -- this session's established idempotency
            # convention (e.g. OperationResourceService.cancel on an already-cancelled resource).
            await self._audit(
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                correlation_id=correlation_id,
                notification_id=notification_id,
                result_code="notification_mark_read_idempotent",
            )
            return notification
        now = self._clock()
        updated = replace(notification, read_at=now)
        if not await self._repository.update(expected=notification, replacement=updated):
            raise NotificationError("notification_transition_conflict")
        await self._audit(
            subject_id=actor.subject_id,
            actor_type=actor.kind.value,
            authentication_method=actor.authentication_method.value,
            assurance_level=actor.assurance_level.value,
            correlation_id=correlation_id,
            notification_id=notification_id,
            result_code="notification_marked_read",
        )
        return updated

    async def _audit(
        self,
        *,
        subject_id: str,
        actor_type: str,
        authentication_method: str | None,
        assurance_level: str | None,
        correlation_id: str,
        notification_id: str | None,
        result_code: str,
        outcome: str = "succeeded",
        target_metadata: tuple[tuple[str, str], ...] = (),
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.notification",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=subject_id,
                actor_type=actor_type,
                authentication_method=authentication_method,
                assurance_level=assurance_level,
                permission_id=None,
                resource_type=_RESOURCE_TYPE,
                scope_reference=notification_id,
                decision_id=None,
                outcome=outcome,
                result_code=result_code,
                target_metadata=target_metadata,
            )
        )
