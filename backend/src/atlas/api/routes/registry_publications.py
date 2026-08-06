from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.registry_publication_schemas import (
    ConnectorRegistryPublicationInput,
    ConnectorRegistryPublicationReceiptData,
    ConnectorRegistryPublicationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_registry_publication_create,
    authorize_connector_registry_publication_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.registry_publication import RegistryPublicationService
from atlas.modules.connectors.application.registry_publication_ports import (
    RegistryPublicationError,
)
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationReceipt,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/registry-publication-receipts", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: RegistryPublicationError) -> NoReturn:
    if error.code.endswith(("mfa_required", "separation_required")):
        status = 403
    elif error.code.endswith("not_found"):
        status = 404
    elif error.code.endswith(("invalid", "required")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="Connector registry publication unavailable",
        detail="The governed connector registry publication operation could not be completed.",
    ) from error


def _response(
    receipt: ConnectorInternalRegistryPublicationReceipt, request: Request, response: Response
) -> ConnectorRegistryPublicationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorRegistryPublicationResponse(
        data=ConnectorRegistryPublicationReceiptData.from_domain(receipt),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorRegistryPublicationResponse, status_code=201)
async def create_connector_registry_publication_receipt(
    payload: ConnectorRegistryPublicationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_registry_publication_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorRegistryPublicationResponse:
    service: RegistryPublicationService = request.app.state.registry_publication_service
    try:
        receipt = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except RegistryPublicationError as error:
        _raise(error)
    return _response(receipt, request, response)


@router.get("/{receipt_id}", response_model=ConnectorRegistryPublicationResponse)
async def get_connector_registry_publication_receipt(
    receipt_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_registry_publication_read)
    ],
) -> ConnectorRegistryPublicationResponse:
    service: RegistryPublicationService = request.app.state.registry_publication_service
    try:
        receipt = await service.get(
            actor=subject,
            receipt_id=receipt_id,
            correlation_id=str(request.state.correlation_id),
        )
    except RegistryPublicationError as error:
        _raise(error)
    return _response(receipt, request, response)
