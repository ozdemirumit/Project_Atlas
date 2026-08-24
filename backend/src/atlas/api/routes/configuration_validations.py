from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.configuration_validation_schemas import (
    ConnectorConfigurationValidationData,
    ConnectorConfigurationValidationInput,
    ConnectorConfigurationValidationInventoryData,
    ConnectorConfigurationValidationInventoryResponse,
    ConnectorConfigurationValidationOptionData,
    ConnectorConfigurationValidationOptionsResponse,
    ConnectorConfigurationValidationResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_configuration_validation_create,
    authorize_connector_configuration_validation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.configuration_validation import (
    ConnectorConfigurationValidationService,
)
from atlas.modules.connectors.application.configuration_validation_ports import (
    ConnectorConfigurationValidationError,
)
from atlas.modules.connectors.domain.configuration_validation import (
    ConnectorConfigurationValidationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/configuration-validations", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorConfigurationValidationError) -> NoReturn:
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
        title="Connector configuration validation unavailable",
        detail="The governed connector configuration validation could not be completed.",
    ) from error


def _response(
    record: ConnectorConfigurationValidationRecord, request: Request, response: Response
) -> ConnectorConfigurationValidationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorConfigurationValidationResponse(
        data=ConnectorConfigurationValidationData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("", response_model=ConnectorConfigurationValidationInventoryResponse)
async def list_connector_configuration_validations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_configuration_validation_read)
    ],
    source_assignment_id: Annotated[
        str | None, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    ] = None,
) -> ConnectorConfigurationValidationInventoryResponse:
    service: ConnectorConfigurationValidationService = (
        request.app.state.configuration_validation_service
    )
    try:
        records = await service.list_validations(
            actor=subject,
            source_assignment_id=source_assignment_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorConfigurationValidationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorConfigurationValidationInventoryResponse(
        data=tuple(
            ConnectorConfigurationValidationInventoryData.from_domain(record) for record in records
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/options", response_model=ConnectorConfigurationValidationOptionsResponse)
async def list_connector_configuration_validation_options(
    source_assignment_id: Annotated[str, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_configuration_validation_read)
    ],
) -> ConnectorConfigurationValidationOptionsResponse:
    service: ConnectorConfigurationValidationService = (
        request.app.state.configuration_validation_service
    )
    try:
        options = await service.list_options(
            actor=subject,
            source_assignment_id=source_assignment_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorConfigurationValidationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorConfigurationValidationOptionsResponse(
        data=tuple(
            ConnectorConfigurationValidationOptionData.from_application(option)
            for option in options
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorConfigurationValidationResponse, status_code=201)
async def create_connector_configuration_validation(
    payload: ConnectorConfigurationValidationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_configuration_validation_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorConfigurationValidationResponse:
    service: ConnectorConfigurationValidationService = (
        request.app.state.configuration_validation_service
    )
    try:
        record = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorConfigurationValidationError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{validation_id}", response_model=ConnectorConfigurationValidationResponse)
async def get_connector_configuration_validation(
    validation_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_configuration_validation_read)
    ],
) -> ConnectorConfigurationValidationResponse:
    service: ConnectorConfigurationValidationService = (
        request.app.state.configuration_validation_service
    )
    try:
        record = await service.get(
            actor=subject,
            validation_id=validation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorConfigurationValidationError as error:
        _raise(error)
    return _response(record, request, response)
