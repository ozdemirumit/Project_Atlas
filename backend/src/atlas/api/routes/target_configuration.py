from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_target_configuration_create,
    authorize_connector_target_configuration_read,
    browser_session_subject,
)
from atlas.api.target_configuration_schemas import (
    ConnectorTargetConfigurationData,
    ConnectorTargetConfigurationInput,
    ConnectorTargetConfigurationResponse,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.target_configuration import (
    ConnectorTargetConfigurationService,
)
from atlas.modules.connectors.application.target_configuration_ports import (
    ConnectorTargetConfigurationError,
)
from atlas.modules.connectors.domain.target_configuration import (
    ConnectorTargetConfigurationBinding,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/target-configuration-bindings", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorTargetConfigurationError) -> NoReturn:
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
        title="Connector target configuration unavailable",
        detail="The governed connector target configuration operation could not be completed.",
    ) from error


def _response(
    binding: ConnectorTargetConfigurationBinding, request: Request, response: Response
) -> ConnectorTargetConfigurationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorTargetConfigurationResponse(
        data=ConnectorTargetConfigurationData.from_domain(binding),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorTargetConfigurationResponse, status_code=201)
async def create_connector_target_configuration(
    payload: ConnectorTargetConfigurationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_target_configuration_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorTargetConfigurationResponse:
    service: ConnectorTargetConfigurationService = request.app.state.target_configuration_service
    try:
        binding = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorTargetConfigurationError as error:
        _raise(error)
    return _response(binding, request, response)


@router.get("/{binding_id}", response_model=ConnectorTargetConfigurationResponse)
async def get_connector_target_configuration(
    binding_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_target_configuration_read)
    ],
) -> ConnectorTargetConfigurationResponse:
    service: ConnectorTargetConfigurationService = request.app.state.target_configuration_service
    try:
        binding = await service.get(
            actor=subject,
            binding_id=binding_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorTargetConfigurationError as error:
        _raise(error)
    return _response(binding, request, response)
