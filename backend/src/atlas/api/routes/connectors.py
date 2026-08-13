from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.connector_schemas import (
    ConnectorPackageAcquisitionData,
    ConnectorPackageAcquisitionInput,
    ConnectorPackageAcquisitionResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_acquire,
    authorize_connector_package_acquisition_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.acquisition import PackageAcquisitionService
from atlas.modules.connectors.application.acquisition_ports import PackageAcquisitionError
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-acquisitions", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key",
    min_length=8,
    max_length=128,
    pattern=r"^[A-Za-z0-9._:-]+$",
)


def _raise(error: PackageAcquisitionError) -> NoReturn:
    if error.code == "package_acquisition_human_required":
        status = 403
    elif error.code.endswith("not_found"):
        status = 404
    elif error.code.endswith(("invalid", "unsupported", "required")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="Connector package acquisition unavailable",
        detail="The package could not be acquired within the governed quarantine boundary.",
    ) from error


def _response(
    acquisition: ConnectorPackageAcquisition, request: Request, response: Response
) -> ConnectorPackageAcquisitionResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageAcquisitionResponse(
        data=ConnectorPackageAcquisitionData.from_domain(acquisition),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPackageAcquisitionResponse, status_code=201)
async def create_package_acquisition(
    payload: ConnectorPackageAcquisitionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_package_acquire)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageAcquisitionResponse:
    service: PackageAcquisitionService = request.app.state.package_acquisition_service
    try:
        acquisition = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageAcquisitionError as error:
        _raise(error)
    return _response(acquisition, request, response)


@router.get(
    "/{acquisition_id}",
    response_model=ConnectorPackageAcquisitionResponse,
)
async def get_package_acquisition(
    acquisition_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_acquisition_read)
    ],
) -> ConnectorPackageAcquisitionResponse:
    service: PackageAcquisitionService = request.app.state.package_acquisition_service
    try:
        acquisition = await service.get(
            actor=subject,
            acquisition_id=acquisition_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageAcquisitionError as error:
        _raise(error)
    return _response(acquisition, request, response)
