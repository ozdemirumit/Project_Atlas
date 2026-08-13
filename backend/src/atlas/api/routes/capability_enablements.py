from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.capability_enablement_schemas import (
    ConnectorCapabilityEnablementData,
    ConnectorCapabilityEnablementInput,
    ConnectorCapabilityEnablementResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_capability_enablement_create,
    authorize_connector_capability_enablement_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.capability_enablement import (
    ConnectorCapabilityEnablementService,
)
from atlas.modules.connectors.application.capability_enablement_ports import (
    ConnectorCapabilityEnablementError,
)
from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/capability-enablements", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorCapabilityEnablementError) -> NoReturn:
    code = str(error)
    if code.endswith(("human_required", "separation_required")):
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
        title="Connector capability enablement unavailable",
        detail="The governed connector capability enablement could not be completed.",
    ) from error


def _response(
    record: ConnectorCapabilityEnablementRecord, request: Request, response: Response
) -> ConnectorCapabilityEnablementResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorCapabilityEnablementResponse(
        data=ConnectorCapabilityEnablementData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorCapabilityEnablementResponse, status_code=201)
async def create_connector_capability_enablement(
    payload: ConnectorCapabilityEnablementInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_capability_enablement_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorCapabilityEnablementResponse:
    service: ConnectorCapabilityEnablementService = request.app.state.capability_enablement_service
    try:
        record = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorCapabilityEnablementError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{enablement_id}", response_model=ConnectorCapabilityEnablementResponse)
async def get_connector_capability_enablement(
    enablement_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_capability_enablement_read)
    ],
) -> ConnectorCapabilityEnablementResponse:
    service: ConnectorCapabilityEnablementService = request.app.state.capability_enablement_service
    try:
        record = await service.get(
            actor=subject,
            enablement_id=enablement_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorCapabilityEnablementError as error:
        _raise(error)
    return _response(record, request, response)
