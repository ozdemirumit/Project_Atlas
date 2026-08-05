from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.contract_validation_schemas import (
    ConnectorPackageContractValidationData,
    ConnectorPackageContractValidationInput,
    ConnectorPackageContractValidationResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_contract_validation_create,
    authorize_connector_package_contract_validation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.contract_validation import (
    PackageContractValidationService,
)
from atlas.modules.connectors.application.contract_validation_ports import (
    PackageContractValidationError,
)
from atlas.modules.connectors.domain.contract_validation import ConnectorPackageContractValidation
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-contract-validations", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: PackageContractValidationError) -> NoReturn:
    if error.code == "package_contract_enterprise_human_mfa_required":
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
        title="Connector package contract validation unavailable",
        detail="The package could not be validated within the governed static contract boundary.",
    ) from error


def _response(
    validation: ConnectorPackageContractValidation,
    request: Request,
    response: Response,
) -> ConnectorPackageContractValidationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageContractValidationResponse(
        data=ConnectorPackageContractValidationData.from_domain(validation),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPackageContractValidationResponse, status_code=201)
async def create_package_contract_validation(
    payload: ConnectorPackageContractValidationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_package_contract_validation_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageContractValidationResponse:
    service: PackageContractValidationService = (
        request.app.state.package_contract_validation_service
    )
    try:
        validation = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageContractValidationError as error:
        _raise(error)
    return _response(validation, request, response)


@router.get("/{validation_id}", response_model=ConnectorPackageContractValidationResponse)
async def get_package_contract_validation(
    validation_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_package_contract_validation_read),
    ],
) -> ConnectorPackageContractValidationResponse:
    service: PackageContractValidationService = (
        request.app.state.package_contract_validation_service
    )
    try:
        validation = await service.get(
            actor=subject,
            validation_id=validation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageContractValidationError as error:
        _raise(error)
    return _response(validation, request, response)
