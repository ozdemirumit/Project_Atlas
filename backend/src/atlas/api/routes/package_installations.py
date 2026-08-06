from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.package_installation_schemas import (
    ConnectorPackageInstallationInput,
    ConnectorPackageInstallationReceiptData,
    ConnectorPackageInstallationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_installation_create,
    authorize_connector_package_installation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.package_installation import PackageInstallationService
from atlas.modules.connectors.application.package_installation_ports import PackageInstallationError
from atlas.modules.connectors.domain.package_installation import ConnectorPackageInstallationReceipt
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-installation-receipts", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: PackageInstallationError) -> NoReturn:
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
        title="Connector package installation unavailable",
        detail="The governed connector package installation operation could not be completed.",
    ) from error


def _response(
    receipt: ConnectorPackageInstallationReceipt, request: Request, response: Response
) -> ConnectorPackageInstallationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageInstallationResponse(
        data=ConnectorPackageInstallationReceiptData.from_domain(receipt),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPackageInstallationResponse, status_code=201)
async def create_connector_package_installation_receipt(
    payload: ConnectorPackageInstallationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_installation_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageInstallationResponse:
    service: PackageInstallationService = request.app.state.package_installation_service
    try:
        receipt = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageInstallationError as error:
        _raise(error)
    return _response(receipt, request, response)


@router.get("/{receipt_id}", response_model=ConnectorPackageInstallationResponse)
async def get_connector_package_installation_receipt(
    receipt_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_installation_read)
    ],
) -> ConnectorPackageInstallationResponse:
    service: PackageInstallationService = request.app.state.package_installation_service
    try:
        receipt = await service.get(
            actor=subject,
            receipt_id=receipt_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageInstallationError as error:
        _raise(error)
    return _response(receipt, request, response)
