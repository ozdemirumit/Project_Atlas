from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.instance_creation_schemas import (
    ConnectorInstanceCreationInput,
    ConnectorInstanceCreationResponse,
    ConnectorInstanceRecordData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_instance_create,
    authorize_connector_instance_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.instance_creation import (
    ConnectorInstanceCreationService,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceCreationError,
)
from atlas.modules.connectors.domain.instance_creation import ConnectorInstanceRecord
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/instances", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorInstanceCreationError) -> NoReturn:
    code = str(error)
    if code.endswith(("mfa_required", "separation_required")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith(("invalid", "required")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Connector instance creation unavailable",
        detail="The governed connector instance operation could not be completed.",
    ) from error


def _response(
    record: ConnectorInstanceRecord, request: Request, response: Response
) -> ConnectorInstanceCreationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorInstanceCreationResponse(
        data=ConnectorInstanceRecordData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorInstanceCreationResponse, status_code=201)
async def create_connector_instance(
    payload: ConnectorInstanceCreationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_instance_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorInstanceCreationResponse:
    service: ConnectorInstanceCreationService = (
        request.app.state.connector_instance_creation_service
    )
    try:
        record = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorInstanceCreationError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{record_id}", response_model=ConnectorInstanceCreationResponse)
async def get_connector_instance(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_instance_read)],
) -> ConnectorInstanceCreationResponse:
    service: ConnectorInstanceCreationService = (
        request.app.state.connector_instance_creation_service
    )
    try:
        record = await service.get(
            actor=subject,
            record_id=record_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInstanceCreationError as error:
        _raise(error)
    return _response(record, request, response)
