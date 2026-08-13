from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schema_semantics_validation_schemas import (
    ConnectorPackageSchemaSemanticsValidationData,
    ConnectorPackageSchemaSemanticsValidationInput,
    ConnectorPackageSchemaSemanticsValidationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_schema_semantics_validation_create,
    authorize_connector_package_schema_semantics_validation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.schema_semantics_validation import (
    PackageSchemaSemanticsValidationService,
)
from atlas.modules.connectors.application.schema_semantics_validation_ports import (
    PackageSchemaSemanticsValidationError,
)
from atlas.modules.connectors.domain.schema_semantics_validation import (
    ConnectorPackageSchemaSemanticsValidation,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-schema-semantics-validations", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: PackageSchemaSemanticsValidationError) -> NoReturn:
    if error.code == "package_schema_semantics_human_required":
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
        title="Connector package schema semantics validation unavailable",
        detail="The package could not be validated within the governed schema semantics boundary.",
    ) from error


def _response(
    validation: ConnectorPackageSchemaSemanticsValidation,
    request: Request,
    response: Response,
) -> ConnectorPackageSchemaSemanticsValidationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageSchemaSemanticsValidationResponse(
        data=ConnectorPackageSchemaSemanticsValidationData.from_domain(validation),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPackageSchemaSemanticsValidationResponse, status_code=201)
async def create_package_schema_semantics_validation(
    payload: ConnectorPackageSchemaSemanticsValidationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_package_schema_semantics_validation_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageSchemaSemanticsValidationResponse:
    service: PackageSchemaSemanticsValidationService = (
        request.app.state.package_schema_semantics_validation_service
    )
    try:
        validation = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageSchemaSemanticsValidationError as error:
        _raise(error)
    return _response(validation, request, response)


@router.get("/{validation_id}", response_model=ConnectorPackageSchemaSemanticsValidationResponse)
async def get_package_schema_semantics_validation(
    validation_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_package_schema_semantics_validation_read),
    ],
) -> ConnectorPackageSchemaSemanticsValidationResponse:
    service: PackageSchemaSemanticsValidationService = (
        request.app.state.package_schema_semantics_validation_service
    )
    try:
        validation = await service.get(
            actor=subject,
            validation_id=validation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageSchemaSemanticsValidationError as error:
        _raise(error)
    return _response(validation, request, response)
