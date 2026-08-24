from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.bounded_invocation_schemas import (
    ConnectorBoundedInvocationData,
    ConnectorBoundedInvocationInput,
    ConnectorBoundedInvocationInventoryResponse,
    ConnectorBoundedInvocationOptionData,
    ConnectorBoundedInvocationOptionsResponse,
    ConnectorBoundedInvocationResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_bounded_invocation_create,
    authorize_connector_bounded_invocation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.bounded_invocation import (
    ConnectorBoundedInvocationService,
)
from atlas.modules.connectors.application.bounded_invocation_ports import (
    ConnectorBoundedInvocationError,
    ConnectorBoundedInvocationUncertainError,
)
from atlas.modules.connectors.domain.bounded_invocation import (
    ConnectorBoundedInvocationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/bounded-invocations", tags=["connectors"])
STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorBoundedInvocationError) -> NoReturn:
    code = str(error)
    if isinstance(error, ConnectorBoundedInvocationUncertainError):
        status = 503
    elif code.endswith(("required", "denied", "separation_required")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith(("invalid", "integrity_failed")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Bounded connector invocation unavailable",
        detail=(
            "The bounded invocation did not produce a reusable authorization. "
            "Uncertain attempts must not be retried."
        ),
    ) from error


def _response(
    record: ConnectorBoundedInvocationRecord,
    request: Request,
    response: Response,
) -> ConnectorBoundedInvocationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorBoundedInvocationResponse(
        data=ConnectorBoundedInvocationData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("", response_model=ConnectorBoundedInvocationInventoryResponse)
async def list_connector_bounded_invocations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_bounded_invocation_read)
    ],
    source_authorization_id: Annotated[str | None, Query(pattern=STABLE_ID)] = None,
) -> ConnectorBoundedInvocationInventoryResponse:
    service: ConnectorBoundedInvocationService = request.app.state.bounded_invocation_service
    try:
        records = await service.list_invocations(
            actor=subject,
            source_authorization_id=source_authorization_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorBoundedInvocationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorBoundedInvocationInventoryResponse(
        data=tuple(ConnectorBoundedInvocationData.from_domain(record) for record in records),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/options", response_model=ConnectorBoundedInvocationOptionsResponse)
async def list_connector_bounded_invocation_options(
    source_authorization_id: Annotated[str, Query(pattern=STABLE_ID)],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_bounded_invocation_read)
    ],
) -> ConnectorBoundedInvocationOptionsResponse:
    service: ConnectorBoundedInvocationService = request.app.state.bounded_invocation_service
    try:
        options = await service.list_options(
            actor=subject,
            source_authorization_id=source_authorization_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorBoundedInvocationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorBoundedInvocationOptionsResponse(
        data=tuple(
            ConnectorBoundedInvocationOptionData.from_application(option) for option in options
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorBoundedInvocationResponse, status_code=201)
async def create_connector_bounded_invocation(
    payload: ConnectorBoundedInvocationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_bounded_invocation_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorBoundedInvocationResponse:
    service: ConnectorBoundedInvocationService = request.app.state.bounded_invocation_service
    try:
        record = await service.create(
            actor=subject,
            source_authorization_id=payload.source_authorization_id,
            source_authorization_digest=payload.source_authorization_digest,
            package_digest=payload.package_digest,
            invocation_policy_id=payload.invocation_policy_id,
            invocation_policy_digest=payload.invocation_policy_digest,
            purpose=payload.purpose,
            irreversible_consumption_acknowledged=(
                payload.acknowledged_authorization_is_consumed_once_without_retry_on_uncertain_outcome
            ),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorBoundedInvocationError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{invocation_id}", response_model=ConnectorBoundedInvocationResponse)
async def get_connector_bounded_invocation(
    invocation_id: Annotated[str, Path(pattern=STABLE_ID)],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_bounded_invocation_read)
    ],
) -> ConnectorBoundedInvocationResponse:
    service: ConnectorBoundedInvocationService = request.app.state.bounded_invocation_service
    try:
        record = await service.get(
            actor=subject,
            invocation_id=invocation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorBoundedInvocationError as error:
        _raise(error)
    return _response(record, request, response)
