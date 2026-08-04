from __future__ import annotations

import base64
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.session_schemas import SessionCreatePayload, SessionCreateResponse, SessionData
from atlas.modules.identity.application.sessions import SessionOperationsError, SessionService
from atlas.modules.identity.domain.models import AuthenticationInput

router = APIRouter(prefix="/authentication/sessions", tags=["authentication"])


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
    response.headers["Cache-Control"] = "no-store"
