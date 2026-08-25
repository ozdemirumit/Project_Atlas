from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request, Response

from atlas.api.connector_connection_test_schemas import (
    BundledConnectionConfigurationData,
    BundledConnectionConfigurationInput,
    BundledConnectionConfigurationResponse,
    ConnectorConnectionTestData,
    ConnectorConnectionTestResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_target_session_create,
    authorize_connector_target_session_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.bundled_connection_configuration import (
    BundledConnectionConfigurationService,
)
from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationError,
)
from atlas.modules.connectors.application.connection_test import ConnectorConnectionTestService
from atlas.modules.connectors.application.connection_test_ports import ConnectorConnectionTestError
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/bundled-instances", tags=["connectors"])


def _raise(error: RuntimeError) -> NoReturn:
    code = str(error)
    if code.endswith(("only", "required")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    else:
        status = 422
    raise AtlasError(
        status=status,
        code=code,
        title="Bundled connector connection operation unavailable",
        detail="The bounded development connector operation could not be completed.",
    ) from error


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


@router.put(
    "/{instance_id}/connection-configuration",
    response_model=BundledConnectionConfigurationResponse,
)
async def configure_bundled_connection(
    instance_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: BundledConnectionConfigurationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_target_session_create)],
) -> BundledConnectionConfigurationResponse:
    service: BundledConnectionConfigurationService = (
        request.app.state.bundled_connection_configuration_service
    )
    if payload.secret is not None:
        _raise(
            BundledConnectionConfigurationError(
                "bundled_connection_configuration_secret_material_forbidden"
            )
        )
    try:
        record = await service.configure(
            actor=subject,
            instance_id=instance_id,
            hostname=payload.hostname,
            port=payload.port,
            trust_profile_id=payload.trust_profile_id,
            secret_reference_id=payload.secret_reference_id,
            correlation_id=str(request.state.correlation_id),
        )
    except BundledConnectionConfigurationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return BundledConnectionConfigurationResponse(
        data=BundledConnectionConfigurationData.from_domain(record), meta=_meta(request)
    )


@router.get(
    "/{instance_id}/connection-configuration",
    response_model=BundledConnectionConfigurationResponse,
)
async def get_bundled_connection(
    instance_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_target_session_read)],
) -> BundledConnectionConfigurationResponse:
    service: BundledConnectionConfigurationService = (
        request.app.state.bundled_connection_configuration_service
    )
    try:
        record = await service.get(
            actor=subject,
            instance_id=instance_id,
            correlation_id=str(request.state.correlation_id),
        )
    except BundledConnectionConfigurationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return BundledConnectionConfigurationResponse(
        data=BundledConnectionConfigurationData.from_domain(record), meta=_meta(request)
    )


@router.post("/{instance_id}/connection-tests", response_model=ConnectorConnectionTestResponse)
async def test_connector_connection(
    instance_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_target_session_read)],
) -> ConnectorConnectionTestResponse:
    service: ConnectorConnectionTestService = request.app.state.connector_connection_test_service
    try:
        result = await service.test(
            actor=subject,
            instance_id=instance_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorConnectionTestError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorConnectionTestResponse(
        data=ConnectorConnectionTestData.from_domain(result), meta=_meta(request)
    )


@router.get(
    "/{instance_id}/connection-tests/latest",
    response_model=ConnectorConnectionTestResponse,
)
async def get_latest_connector_connection_test(
    instance_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_target_session_read)],
) -> ConnectorConnectionTestResponse:
    service: ConnectorConnectionTestService = request.app.state.connector_connection_test_service
    try:
        result = await service.latest(
            actor=subject,
            instance_id=instance_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorConnectionTestError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorConnectionTestResponse(
        data=ConnectorConnectionTestData.from_domain(result), meta=_meta(request)
    )
