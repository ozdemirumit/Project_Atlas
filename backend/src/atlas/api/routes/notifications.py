"""docs/037_Approval_Workflow.md SS20/SS22/SS29 (pass 38): the real, RBAC-gated, pull-based
notification inbox. See `atlas.modules.notifications.domain.models` for why this is a dedicated
cross-cutting module rather than living under `approvals`, and
`atlas.modules.notifications.application.subscriber` for how a real notification gets created in
the first place (a real event-bus subscriber reacting to an already-committed approval domain
event -- never written directly from an HTTP request).

Both routes are absolute about ownership: a notification is inherently personal, so unlike
`GET /approvals` (which allows a broader eligible-approver/owner visibility) there is no
cross-subject read path here at all -- a caller only ever sees or marks their own
`recipient_subject_id`, enforced by `NotificationService` itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.notification_schemas import (
    NotificationData,
    NotificationListData,
    NotificationListResponse,
    NotificationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_notification_read
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.notifications.application.ports import NotificationError
from atlas.modules.notifications.application.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _error(exc: NotificationError) -> AtlasError:
    if exc.code == "notification_not_found":
        status = 404
    elif exc.code in {"notification_list_limit_invalid", "notification_list_cursor_invalid"}:
        status = 422
    else:
        status = 409
    return AtlasError(
        status=status,
        code=exc.code,
        title="Notification unavailable",
        detail=exc.detail,
    )


def _environment_id(request: Request) -> str:
    settings = request.app.state.settings
    return f"environment.{settings.environment}"


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_notification_read)],
    unread_only: bool = False,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationListResponse:
    now = datetime.now(UTC)
    service: NotificationService = request.app.state.notification_service
    try:
        page = await service.list_for_subject(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=_environment_id(request),
            unread_only=unread_only,
            cursor=cursor,
            limit=limit,
            correlation_id=str(request.state.correlation_id),
        )
    except NotificationError as exc:
        raise _error(exc) from exc
    response.headers["Cache-Control"] = "no-store"
    return NotificationListResponse(
        data=NotificationListData(
            items=[NotificationData.from_domain(item) for item in page.items],
            next_cursor=page.next_cursor,
            limit=page.limit,
        ),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_notification_read)],
) -> NotificationResponse:
    now = datetime.now(UTC)
    service: NotificationService = request.app.state.notification_service
    try:
        notification = await service.mark_read(
            actor=subject,
            notification_id=notification_id,
            organization_id=subject.organization_id,
            environment_id=_environment_id(request),
            correlation_id=str(request.state.correlation_id),
        )
    except NotificationError as exc:
        raise _error(exc) from exc
    response.headers["Cache-Control"] = "no-store"
    return NotificationResponse(
        data=NotificationData.from_domain(notification),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
