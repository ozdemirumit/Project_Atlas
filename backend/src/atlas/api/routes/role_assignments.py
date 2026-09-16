from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.role_assignment_schemas import (
    RoleAssignmentData,
    RoleAssignmentGrantInput,
    RoleAssignmentGrantResponse,
    RoleAssignmentListResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_rbac_role_assignment_create,
    authorize_rbac_role_assignment_read,
    browser_session_subject,
)
from atlas.modules.authorization.application.role_assignment_grant import (
    RoleAssignmentGrantError,
    RoleAssignmentGrantService,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/authorization/role-assignments", tags=["authorization"])


def _raise(error: RoleAssignmentGrantError) -> NoReturn:
    code = error.code
    status = 403 if code.endswith("required") else 422
    raise AtlasError(
        status=status,
        code=code,
        title="Role-assignment grant unavailable",
        detail="The role-assignment operation could not be completed.",
    ) from error


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


@router.post("", response_model=RoleAssignmentGrantResponse)
async def grant_role_assignment(
    payload: RoleAssignmentGrantInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_rbac_role_assignment_create)],
) -> RoleAssignmentGrantResponse:
    service: RoleAssignmentGrantService = request.app.state.role_assignment_grant_service
    try:
        created = await service.grant(
            actor=subject,
            subject_id=payload.subject_id,
            role_id=payload.role_id,
            correlation_id=str(request.state.correlation_id),
        )
    except RoleAssignmentGrantError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return RoleAssignmentGrantResponse(
        data=tuple(RoleAssignmentData.from_domain(item) for item in created), meta=_meta(request)
    )


@router.get("", response_model=RoleAssignmentListResponse)
async def list_role_assignments(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_rbac_role_assignment_read)],
    subject_id: Annotated[str, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
) -> RoleAssignmentListResponse:
    service: RoleAssignmentGrantService = request.app.state.role_assignment_grant_service
    active = await service.list_active(actor=subject, subject_id=subject_id)
    response.headers["Cache-Control"] = "no-store"
    return RoleAssignmentListResponse(
        data=tuple(RoleAssignmentData.from_domain(item) for item in active), meta=_meta(request)
    )
