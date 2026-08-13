from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.runtime_activation_schemas import (
    ConnectorRuntimeActivationData,
    ConnectorRuntimeActivationInput,
    ConnectorRuntimeActivationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_runtime_activation_create,
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


def _response(
    record: ConnectorRuntimeActivationRecord,
    request: Request,
    response: Response,
) -> ConnectorRuntimeActivationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorRuntimeActivationResponse(
        data=ConnectorRuntimeActivationData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorRuntimeActivationResponse, status_code=201)
async def create_connector_runtime_activation(
    payload: ConnectorRuntimeActivationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_runtime_activation_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorRuntimeActivationResponse:
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


@router.get("/{activation_id}", response_model=ConnectorRuntimeActivationResponse)
async def get_connector_runtime_activation(
    activation_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_runtime_activation_read)
    ],
) -> ConnectorRuntimeActivationResponse:
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
