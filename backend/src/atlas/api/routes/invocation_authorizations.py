from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.invocation_authorization_schemas import (
    ConnectorInvocationAuthorizationData,
    ConnectorInvocationAuthorizationInput,
    ConnectorInvocationAuthorizationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_invocation_authorization_create,
    authorize_connector_invocation_authorization_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.invocation_authorization import (
    ConnectorInvocationAuthorizationService,
)
from atlas.modules.connectors.application.invocation_authorization_ports import (
    ConnectorInvocationAuthorizationError,
)
from atlas.modules.connectors.domain.invocation_authorization import (
    ConnectorInvocationAuthorizationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/invocation-authorizations", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorInvocationAuthorizationError) -> NoReturn:
    code = str(error)
    if code.endswith(("required", "denied", "mfa_required", "separation_required")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith(("invalid", "integrity_failed")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Connector invocation authorization unavailable",
        detail="The governed connector invocation authorization could not be completed.",
    ) from error


def _response(
    record: ConnectorInvocationAuthorizationRecord,
    request: Request,
    response: Response,
) -> ConnectorInvocationAuthorizationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorInvocationAuthorizationResponse(
        data=ConnectorInvocationAuthorizationData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorInvocationAuthorizationResponse, status_code=201)
async def create_connector_invocation_authorization(
    payload: ConnectorInvocationAuthorizationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_invocation_authorization_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorInvocationAuthorizationResponse:
    service: ConnectorInvocationAuthorizationService = (
        request.app.state.invocation_authorization_service
    )
    try:
        record = await service.create(
            actor=subject,
            source_target_session_verification_id=(payload.source_target_session_verification_id),
            source_target_session_digest=payload.source_target_session_digest,
            package_digest=payload.package_digest,
            capability_id=payload.capability_id,
            invocation_profile_id=payload.invocation_profile_id,
            invocation_profile_digest=payload.invocation_profile_digest,
            input_envelope_id=payload.input_envelope_id,
            input_envelope_digest=payload.input_envelope_digest,
            authorization_policy_id=payload.authorization_policy_id,
            authorization_policy_digest=payload.authorization_policy_digest,
            purpose=payload.purpose,
            single_use_boundary_acknowledged=(
                payload.acknowledged_single_use_authorization_grants_no_invocation_schedule_execution_or_deployment
            ),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInvocationAuthorizationError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{authorization_id}", response_model=ConnectorInvocationAuthorizationResponse)
async def get_connector_invocation_authorization(
    authorization_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_invocation_authorization_read)
    ],
) -> ConnectorInvocationAuthorizationResponse:
    service: ConnectorInvocationAuthorizationService = (
        request.app.state.invocation_authorization_service
    )
    try:
        record = await service.get(
            actor=subject,
            authorization_id=authorization_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInvocationAuthorizationError as error:
        _raise(error)
    return _response(record, request, response)
