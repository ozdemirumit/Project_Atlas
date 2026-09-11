"""docs/050_API.md SS15/SS19/SS20: the generic operation-resource poll/cancel routes.

`GET /operations/{operation_id}` polls the real current state of a durable operation resource.
`POST /operations/{operation_id}/cancellations` is the explicit, idempotent cancellation command
SS20 requires -- CSRF-protected `browser_session_subject` because it is a real mutating human
command, not a background transition.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.operation_schemas import (
    OperationCancellationInput,
    OperationResourceData,
    OperationResourceResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operation_resource_cancel,
    authorize_operation_resource_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.operations.application.ports import OperationResourceError
from atlas.modules.operations.application.service import OperationResourceService

router = APIRouter(prefix="/operations", tags=["operations"])


def _raise(error: OperationResourceError) -> NoReturn:
    code = error.code
    if code.endswith(("required", "denied")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith(("invalid", "reason_required")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Operation resource request unavailable",
        detail="Operation resources reflect only real, already-recorded background work.",
    ) from error


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


@router.get("/{operation_id}", response_model=OperationResourceResponse, status_code=200)
async def get_operation_resource(
    operation_id: str,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_operation_resource_read)],
) -> OperationResourceResponse:
    service: OperationResourceService = request.app.state.operation_resource_service
    try:
        resource = await service.get(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            operation_id=operation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationResourceError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return OperationResourceResponse(
        data=OperationResourceData.from_domain(resource), meta=_meta(request)
    )


@router.post(
    "/{operation_id}/cancellations", response_model=OperationResourceResponse, status_code=200
)
async def cancel_operation_resource(
    operation_id: str,
    payload: OperationCancellationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_operation_resource_cancel)],
) -> OperationResourceResponse:
    service: OperationResourceService = request.app.state.operation_resource_service
    try:
        resource = await service.cancel(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            operation_id=operation_id,
            reason=payload.reason,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationResourceError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return OperationResourceResponse(
        data=OperationResourceData.from_domain(resource), meta=_meta(request)
    )
