from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.package_signing_schemas import (
    ConnectorPackageSigningInput,
    ConnectorPackageSigningReceiptData,
    ConnectorPackageSigningResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_signing_create,
    authorize_connector_package_signing_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.package_signing import PackageSigningService
from atlas.modules.connectors.application.package_signing_ports import PackageSigningError
from atlas.modules.connectors.domain.package_signing import ConnectorPackageSigningReceipt
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-signing-receipts", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: PackageSigningError) -> NoReturn:
    if error.code.endswith(("human_required", "separation_required")):
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
        title="Connector package signing unavailable",
        detail="The governed connector package signing operation could not be completed.",
    ) from error


def _response(
    receipt: ConnectorPackageSigningReceipt, request: Request, response: Response
) -> ConnectorPackageSigningResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageSigningResponse(
        data=ConnectorPackageSigningReceiptData.from_domain(receipt),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPackageSigningResponse, status_code=201)
async def create_connector_package_signing_receipt(
    payload: ConnectorPackageSigningInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_signing_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageSigningResponse:
    service: PackageSigningService = request.app.state.package_signing_service
    try:
        receipt = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageSigningError as error:
        _raise(error)
    return _response(receipt, request, response)


@router.get("/{receipt_id}", response_model=ConnectorPackageSigningResponse)
async def get_connector_package_signing_receipt(
    receipt_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_package_signing_read)],
) -> ConnectorPackageSigningResponse:
    service: PackageSigningService = request.app.state.package_signing_service
    try:
        receipt = await service.get(
            actor=subject,
            receipt_id=receipt_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageSigningError as error:
        _raise(error)
    return _response(receipt, request, response)
