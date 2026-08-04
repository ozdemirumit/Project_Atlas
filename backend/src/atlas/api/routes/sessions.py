from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_session_self_read,
    authorize_session_self_revoke,
)
from atlas.api.session_schemas import (
    SessionCreatePayload,
    SessionCreateResponse,
    SessionData,
    SessionInventoryData,
    SessionInventoryItem,
    SessionInventoryResponse,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.application.sessions import SessionOperationsError, SessionService
from atlas.modules.identity.domain.models import AuthenticatedSubject, AuthenticationInput

router = APIRouter(prefix="/authentication/sessions", tags=["authentication"])


def _clear_session_cookies(response: Response, request: Request) -> None:
    settings = request.app.state.settings
    response.delete_cookie(
        settings.session_cookie_name,
        path="/api",
        secure=settings.environment == "production",
        httponly=True,
        samesite="strict",
    )
    response.delete_cookie(
        settings.csrf_cookie_name,
        path="/",
        secure=settings.environment == "production",
        httponly=False,
        samesite="strict",
    )


@router.post("", response_model=SessionCreateResponse, status_code=201)
async def create_session(
    payload: SessionCreatePayload,
    request: Request,
    response: Response,
) -> SessionCreateResponse:
    settings = request.app.state.settings
    service: SessionService = request.app.state.session_service
    encoded = base64.b64encode(
        f"{payload.username}:{payload.password.get_secret_value()}".encode()
    ).decode()
    try:
        issued = await service.create(
            AuthenticationInput(
                correlation_id=str(request.state.correlation_id),
                authorization_scheme="basic",
                credential=encoded,
            )
        )
    except SessionOperationsError as exc:
        status = 429 if exc.code == "session_limit_exceeded" else 401
        raise AtlasError(
            status=status,
            code=exc.code,
            title="Session unavailable",
            detail="A browser session could not be created.",
        ) from exc
    response.set_cookie(
        key=settings.session_cookie_name,
        value=issued.token,
        max_age=settings.session_absolute_timeout_minutes * 60,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path="/api",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=issued.csrf_token,
        max_age=settings.session_absolute_timeout_minutes * 60,
        httponly=False,
        secure=settings.environment == "production",
        samesite="strict",
        path="/",
    )
    response.headers[settings.csrf_header_name] = issued.csrf_token
    response.headers["Cache-Control"] = "no-store"
    now = datetime.now(UTC)
    return SessionCreateResponse(
        data=SessionData.from_domain(issued.record),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.get("", response_model=SessionInventoryResponse)
async def list_sessions(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_session_self_read)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SessionInventoryResponse:
    service: SessionService = request.app.state.session_service
    inventory = await service.inventory(
        subject.subject_id,
        correlation_id=str(request.state.correlation_id),
        limit=limit,
    )
    current_session_id = getattr(request.state, "authenticated_session_id", None)
    response.headers["Cache-Control"] = "no-store"
    return SessionInventoryResponse(
        data=SessionInventoryData(
            sessions=[
                SessionInventoryItem.from_domain(item, current_session_id=current_session_id)
                for item in inventory.records
            ],
            truncated=inventory.truncated,
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.delete("/current", status_code=204)
async def logout_session(request: Request, response: Response) -> None:
    settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if token is None:
        raise AtlasError(
            status=401,
            code="authentication_required",
            title="Authentication required",
            detail="A valid authenticated identity is required for this operation.",
        )
    service: SessionService = request.app.state.session_service
    try:
        await service.revoke(
            token,
            csrf_token=request.headers.get(settings.csrf_header_name),
            correlation_id=str(request.state.correlation_id),
        )
    except SessionOperationsError as exc:
        status = 403 if exc.code == "csrf_validation_failed" else 401
        raise AtlasError(
            status=status,
            code=exc.code,
            title="Session unavailable",
            detail="The browser session could not be terminated.",
        ) from exc
    _clear_session_cookies(response, request)
    response.headers["Cache-Control"] = "no-store"


@router.delete("/{session_id}", status_code=204)
async def revoke_session(
    session_id: str,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_session_self_revoke)],
) -> None:
    service: SessionService = request.app.state.session_service
    try:
        await service.revoke_by_session_id(
            session_id,
            subject_id=subject.subject_id,
            correlation_id=str(request.state.correlation_id),
        )
    except SessionOperationsError as exc:
        raise AtlasError(
            status=404,
            code="session_not_found",
            title="Session unavailable",
            detail="The requested session is unavailable.",
        ) from exc
    if session_id == getattr(request.state, "authenticated_session_id", None):
        _clear_session_cookies(response, request)
    response.headers["Cache-Control"] = "no-store"
