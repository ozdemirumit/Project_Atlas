from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.authority_behavior_validation_schemas import (
    ConnectorPackageAuthorityBehaviorValidationData,
    ConnectorPackageAuthorityBehaviorValidationInput,
    ConnectorPackageAuthorityBehaviorValidationResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_authority_behavior_validation_create,
    authorize_connector_package_authority_behavior_validation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.authority_behavior_validation import (
    PackageAuthorityBehaviorValidationService,
)
from atlas.modules.connectors.application.authority_behavior_validation_ports import (
    PackageAuthorityBehaviorValidationError,
)
from atlas.modules.connectors.domain.authority_behavior_validation import (
    ConnectorPackageAuthorityBehaviorValidation,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-authority-behavior-validations", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: PackageAuthorityBehaviorValidationError) -> NoReturn:
    if error.code == "package_authority_behavior_enterprise_human_mfa_required":
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
        title="Connector package authority behavior validation unavailable",
        detail="The package could not be validated within the governed authority boundary.",
    ) from error


def _response(
    validation: ConnectorPackageAuthorityBehaviorValidation,
    request: Request,
    response: Response,
) -> ConnectorPackageAuthorityBehaviorValidationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageAuthorityBehaviorValidationResponse(
        data=ConnectorPackageAuthorityBehaviorValidationData.from_domain(validation),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "", response_model=ConnectorPackageAuthorityBehaviorValidationResponse, status_code=201
)
async def create_package_authority_behavior_validation(
    payload: ConnectorPackageAuthorityBehaviorValidationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_package_authority_behavior_validation_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageAuthorityBehaviorValidationResponse:
    service: PackageAuthorityBehaviorValidationService = (
        request.app.state.package_authority_behavior_validation_service
    )
    try:
        validation = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageAuthorityBehaviorValidationError as error:
        _raise(error)
    return _response(validation, request, response)


@router.get("/{validation_id}", response_model=ConnectorPackageAuthorityBehaviorValidationResponse)
async def get_package_authority_behavior_validation(
    validation_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_package_authority_behavior_validation_read),
    ],
) -> ConnectorPackageAuthorityBehaviorValidationResponse:
    service: PackageAuthorityBehaviorValidationService = (
        request.app.state.package_authority_behavior_validation_service
    )
    try:
        validation = await service.get(
            actor=subject,
            validation_id=validation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageAuthorityBehaviorValidationError as error:
        _raise(error)
    return _response(validation, request, response)
