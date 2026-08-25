from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.runtime_activation_schemas import (
    ConnectorRuntimeActivationInput,
    ConnectorRuntimeActivationInventoryData,
    ConnectorRuntimeActivationInventoryResponse,
    ConnectorRuntimeActivationOptionData,
    ConnectorRuntimeActivationOptionsResponse,
    ConnectorRuntimeActivationViewResponse,
)
from atlas.api.runtime_deactivation_schemas import (
    ConnectorRuntimeDeactivationData,
    ConnectorRuntimeDeactivationInput,
    ConnectorRuntimeDeactivationInventoryResponse,
    ConnectorRuntimeDeactivationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_runtime_activation_create,
    authorize_connector_runtime_activation_deactivate,
    authorize_connector_runtime_activation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
)
from atlas.modules.connectors.application.runtime_activation_ports import (
    ConnectorRuntimeActivationError,
)
from atlas.modules.connectors.application.runtime_deactivation import (
    ConnectorRuntimeDeactivationService,
)
from atlas.modules.connectors.application.runtime_deactivation_ports import (
    ConnectorRuntimeDeactivationError,
)
from atlas.modules.connectors.domain.runtime_activation import ConnectorRuntimeActivationRecord
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/runtime-activations", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorRuntimeActivationError) -> NoReturn:
    code = str(error)
    if code.endswith(("required", "human_required", "separation_required")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith("invalid"):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Connector runtime activation unavailable",
        detail="The governed connector runtime activation could not be completed.",
    ) from error


def _raise_deactivation(error: ConnectorRuntimeDeactivationError) -> NoReturn:
    code = str(error)
    if code.endswith(("required", "human_required")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith("invalid"):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Connector runtime deactivation unavailable",
        detail="The connector runtime could not be safely deactivated.",
    ) from error


def _response(
    record: ConnectorRuntimeActivationRecord,
    request: Request,
    response: Response,
) -> ConnectorRuntimeActivationViewResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorRuntimeActivationViewResponse(
        data=ConnectorRuntimeActivationInventoryData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("", response_model=ConnectorRuntimeActivationInventoryResponse)
async def list_connector_runtime_activations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_runtime_activation_read)
    ],
    source_brokerage_authorization_id: Annotated[
        str | None, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    ] = None,
) -> ConnectorRuntimeActivationInventoryResponse:
    service: ConnectorRuntimeActivationService = request.app.state.runtime_activation_service
    try:
        records = await service.list_activations(
            actor=subject,
            source_brokerage_authorization_id=source_brokerage_authorization_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorRuntimeActivationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorRuntimeActivationInventoryResponse(
        data=tuple(
            ConnectorRuntimeActivationInventoryData.from_domain(record) for record in records
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/options", response_model=ConnectorRuntimeActivationOptionsResponse)
async def list_connector_runtime_activation_options(
    source_brokerage_authorization_id: Annotated[str, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_runtime_activation_read)
    ],
) -> ConnectorRuntimeActivationOptionsResponse:
    service: ConnectorRuntimeActivationService = request.app.state.runtime_activation_service
    try:
        options = await service.list_options(
            actor=subject,
            source_brokerage_authorization_id=source_brokerage_authorization_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorRuntimeActivationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorRuntimeActivationOptionsResponse(
        data=tuple(
            ConnectorRuntimeActivationOptionData.from_application(option) for option in options
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorRuntimeActivationViewResponse, status_code=201)
async def create_connector_runtime_activation(
    payload: ConnectorRuntimeActivationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_runtime_activation_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorRuntimeActivationViewResponse:
    service: ConnectorRuntimeActivationService = request.app.state.runtime_activation_service
    try:
        record = await service.create(
            actor=subject,
            source_brokerage_authorization_id=payload.source_brokerage_authorization_id,
            source_brokerage_authorization_digest=(payload.source_brokerage_authorization_digest),
            package_digest=payload.package_digest,
            activation_profile_id=payload.activation_profile_id,
            activation_profile_digest=payload.activation_profile_digest,
            activation_policy_id=payload.activation_policy_id,
            activation_policy_digest=payload.activation_policy_digest,
            purpose=payload.purpose,
            activation_boundary_acknowledged=(
                payload.acknowledged_activation_grants_no_target_connection_invocation_execution_or_deployment
            ),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorRuntimeActivationError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/deactivations",
    response_model=ConnectorRuntimeDeactivationInventoryResponse,
)
async def list_connector_runtime_deactivations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_runtime_activation_read)
    ],
    activation_id: Annotated[
        str | None, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    ] = None,
) -> ConnectorRuntimeDeactivationInventoryResponse:
    service: ConnectorRuntimeDeactivationService = (
        request.app.state.runtime_deactivation_service
    )
    try:
        records = await service.list_deactivations(
            actor=subject,
            activation_id=activation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorRuntimeDeactivationError as error:
        _raise_deactivation(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorRuntimeDeactivationInventoryResponse(
        data=tuple(ConnectorRuntimeDeactivationData.from_domain(record) for record in records),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get(
    "/{activation_id}/deactivations",
    response_model=ConnectorRuntimeDeactivationInventoryResponse,
)
async def list_connector_runtime_activation_deactivations(
    activation_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_runtime_activation_read)
    ],
) -> ConnectorRuntimeDeactivationInventoryResponse:
    service: ConnectorRuntimeDeactivationService = (
        request.app.state.runtime_deactivation_service
    )
    try:
        records = await service.list_deactivations(
            actor=subject,
            activation_id=activation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorRuntimeDeactivationError as error:
        _raise_deactivation(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorRuntimeDeactivationInventoryResponse(
        data=tuple(ConnectorRuntimeDeactivationData.from_domain(record) for record in records),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{activation_id}/deactivations",
    response_model=ConnectorRuntimeDeactivationResponse,
    status_code=201,
)
async def deactivate_connector_runtime_activation(
    activation_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ConnectorRuntimeDeactivationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_runtime_activation_deactivate)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorRuntimeDeactivationResponse:
    service: ConnectorRuntimeDeactivationService = (
        request.app.state.runtime_deactivation_service
    )
    try:
        record = await service.create(
            actor=subject,
            activation_id=activation_id,
            expected_activation_version=payload.expected_activation_version,
            expected_activation_digest=payload.expected_activation_digest,
            reason=payload.reason,
            runtime_only_acknowledged=payload.acknowledged_runtime_only_deactivation,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorRuntimeDeactivationError as error:
        _raise_deactivation(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorRuntimeDeactivationResponse(
        data=ConnectorRuntimeDeactivationData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/{activation_id}", response_model=ConnectorRuntimeActivationViewResponse)
async def get_connector_runtime_activation(
    activation_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_runtime_activation_read)
    ],
) -> ConnectorRuntimeActivationViewResponse:
    service: ConnectorRuntimeActivationService = request.app.state.runtime_activation_service
    try:
        record = await service.get(
            actor=subject,
            activation_id=activation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorRuntimeActivationError as error:
        _raise(error)
    return _response(record, request, response)
