from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.final_validation_schemas import (
    ConnectorPackageFinalValidationData,
    ConnectorPackageFinalValidationInput,
    ConnectorPackageFinalValidationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_final_validation_create,
    authorize_connector_package_final_validation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.final_validation import PackageFinalValidationService
from atlas.modules.connectors.application.final_validation_ports import PackageFinalValidationError
from atlas.modules.connectors.domain.final_validation import ConnectorPackageFinalValidation
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-final-validations", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: PackageFinalValidationError) -> NoReturn:
    if error.code == "package_final_enterprise_human_mfa_required":
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
        title="Connector package final validation unavailable",
        detail="The package evidence could not pass the governed final-validation boundary.",
    ) from error


def _response(
    validation: ConnectorPackageFinalValidation, request: Request, response: Response
) -> ConnectorPackageFinalValidationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageFinalValidationResponse(
        data=ConnectorPackageFinalValidationData.from_domain(validation),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPackageFinalValidationResponse, status_code=201)
async def create_package_final_validation(
    payload: ConnectorPackageFinalValidationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_final_validation_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageFinalValidationResponse:
    service: PackageFinalValidationService = request.app.state.package_final_validation_service
    try:
        validation = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageFinalValidationError as error:
        _raise(error)
    return _response(validation, request, response)


@router.get("/{validation_id}", response_model=ConnectorPackageFinalValidationResponse)
async def get_package_final_validation(
    validation_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_final_validation_read)
    ],
) -> ConnectorPackageFinalValidationResponse:
    service: PackageFinalValidationService = request.app.state.package_final_validation_service
    try:
        validation = await service.get(
            actor=subject,
            validation_id=validation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageFinalValidationError as error:
        _raise(error)
    return _response(validation, request, response)
