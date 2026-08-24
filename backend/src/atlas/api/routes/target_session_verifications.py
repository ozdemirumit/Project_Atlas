from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_target_session_create,
    authorize_connector_target_session_read,
    browser_session_subject,
)
from atlas.api.target_session_schemas import (
    ConnectorTargetSessionData,
    ConnectorTargetSessionInput,
    ConnectorTargetSessionInventoryResponse,
    ConnectorTargetSessionOptionData,
    ConnectorTargetSessionOptionsResponse,
    ConnectorTargetSessionResponse,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.target_session import ConnectorTargetSessionService
from atlas.modules.connectors.application.target_session_ports import ConnectorTargetSessionError
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionVerificationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/target-session-verifications", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorTargetSessionError) -> NoReturn:
    code = str(error)
    if code.endswith(("required", "separation_required")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith("invalid"):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Connector target session verification unavailable",
        detail="The governed connector target session verification could not be completed.",
    ) from error


def _response(
    record: ConnectorTargetSessionVerificationRecord,
    request: Request,
    response: Response,
) -> ConnectorTargetSessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorTargetSessionResponse(
        data=ConnectorTargetSessionData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("", response_model=ConnectorTargetSessionInventoryResponse)
async def list_connector_target_session_verifications(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_target_session_read)],
    source_runtime_activation_id: Annotated[
        str | None, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    ] = None,
) -> ConnectorTargetSessionInventoryResponse:
    service: ConnectorTargetSessionService = request.app.state.target_session_service
    try:
        records = await service.list_verifications(
            actor=subject,
            source_runtime_activation_id=source_runtime_activation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorTargetSessionError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorTargetSessionInventoryResponse(
        data=tuple(ConnectorTargetSessionData.from_domain(record) for record in records),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/options", response_model=ConnectorTargetSessionOptionsResponse)
async def list_connector_target_session_options(
    source_runtime_activation_id: Annotated[str, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_target_session_read)],
) -> ConnectorTargetSessionOptionsResponse:
    service: ConnectorTargetSessionService = request.app.state.target_session_service
    try:
        options = await service.list_options(
            actor=subject,
            source_runtime_activation_id=source_runtime_activation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorTargetSessionError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorTargetSessionOptionsResponse(
        data=tuple(ConnectorTargetSessionOptionData.from_application(option) for option in options),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorTargetSessionResponse, status_code=201)
async def create_connector_target_session_verification(
    payload: ConnectorTargetSessionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_target_session_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorTargetSessionResponse:
    service: ConnectorTargetSessionService = request.app.state.target_session_service
    try:
        record = await service.create(
            actor=subject,
            source_runtime_activation_id=payload.source_runtime_activation_id,
            source_runtime_activation_digest=payload.source_runtime_activation_digest,
            package_digest=payload.package_digest,
            session_profile_id=payload.session_profile_id,
            session_profile_digest=payload.session_profile_digest,
            session_policy_id=payload.session_policy_id,
            session_policy_digest=payload.session_policy_digest,
            purpose=payload.purpose,
            bounded_session_acknowledged=(
                payload.acknowledged_bounded_session_grants_no_invocation_execution_or_deployment
            ),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorTargetSessionError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{verification_id}", response_model=ConnectorTargetSessionResponse)
async def get_connector_target_session_verification(
    verification_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_target_session_read)],
) -> ConnectorTargetSessionResponse:
    service: ConnectorTargetSessionService = request.app.state.target_session_service
    try:
        record = await service.get(
            actor=subject,
            verification_id=verification_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorTargetSessionError as error:
        _raise(error)
    return _response(record, request, response)
