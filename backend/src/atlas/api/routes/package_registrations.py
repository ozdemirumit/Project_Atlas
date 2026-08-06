from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.package_registration_schemas import (
    ConnectorPackageRegistrationInput,
    ConnectorPackageRegistrationRecordData,
    ConnectorPackageRegistrationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_registration_create,
    authorize_connector_package_registration_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.package_registration import PackageRegistrationService
from atlas.modules.connectors.application.package_registration_ports import PackageRegistrationError
from atlas.modules.connectors.domain.package_registration import ConnectorPackageRegistrationRecord
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-registration-records", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: PackageRegistrationError) -> NoReturn:
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
        title="Connector package registration unavailable",
        detail="The governed connector package registration operation could not be completed.",
    ) from error


def _response(
    record: ConnectorPackageRegistrationRecord, request: Request, response: Response
) -> ConnectorPackageRegistrationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageRegistrationResponse(
        data=ConnectorPackageRegistrationRecordData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPackageRegistrationResponse, status_code=201)
async def create_connector_package_registration_record(
    payload: ConnectorPackageRegistrationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_registration_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageRegistrationResponse:
    service: PackageRegistrationService = request.app.state.package_registration_service
    try:
        record = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageRegistrationError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{record_id}", response_model=ConnectorPackageRegistrationResponse)
async def get_connector_package_registration_record(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_registration_read)
    ],
) -> ConnectorPackageRegistrationResponse:
    service: PackageRegistrationService = request.app.state.package_registration_service
    try:
        record = await service.get(
            actor=subject,
            record_id=record_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageRegistrationError as error:
        _raise(error)
    return _response(record, request, response)
