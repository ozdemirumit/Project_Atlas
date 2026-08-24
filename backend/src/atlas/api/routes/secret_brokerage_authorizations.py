from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.secret_brokerage_schemas import (
    ConnectorSecretBrokerageInput,
    ConnectorSecretBrokerageInventoryData,
    ConnectorSecretBrokerageInventoryResponse,
    ConnectorSecretBrokerageOptionData,
    ConnectorSecretBrokerageOptionsResponse,
    ConnectorSecretBrokerageViewResponse,
)
from atlas.api.security import (
    authorize_connector_secret_brokerage_create,
    authorize_connector_secret_brokerage_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.secret_brokerage import (
    ConnectorSecretBrokerageService,
)
from atlas.modules.connectors.application.secret_brokerage_ports import (
    ConnectorSecretBrokerageError,
)
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/secret-brokerage-authorizations", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorSecretBrokerageError) -> NoReturn:
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
        title="Connector secret brokerage unavailable",
        detail="The governed connector secret brokerage authorization could not be completed.",
    ) from error


def _response(
    record: ConnectorSecretBrokerageAuthorizationRecord,
    request: Request,
    response: Response,
) -> ConnectorSecretBrokerageViewResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorSecretBrokerageViewResponse(
        data=ConnectorSecretBrokerageInventoryData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("", response_model=ConnectorSecretBrokerageInventoryResponse)
async def list_connector_secret_brokerage_authorizations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_secret_brokerage_read)],
    source_runtime_trust_grant_id: Annotated[
        str | None, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    ] = None,
) -> ConnectorSecretBrokerageInventoryResponse:
    service: ConnectorSecretBrokerageService = request.app.state.secret_brokerage_service
    try:
        records = await service.list_authorizations(
            actor=subject,
            source_runtime_trust_grant_id=source_runtime_trust_grant_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorSecretBrokerageError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorSecretBrokerageInventoryResponse(
        data=tuple(ConnectorSecretBrokerageInventoryData.from_domain(record) for record in records),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/options", response_model=ConnectorSecretBrokerageOptionsResponse)
async def list_connector_secret_brokerage_options(
    source_runtime_trust_grant_id: Annotated[str, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_secret_brokerage_read)],
) -> ConnectorSecretBrokerageOptionsResponse:
    service: ConnectorSecretBrokerageService = request.app.state.secret_brokerage_service
    try:
        options = await service.list_options(
            actor=subject,
            source_runtime_trust_grant_id=source_runtime_trust_grant_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorSecretBrokerageError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorSecretBrokerageOptionsResponse(
        data=tuple(
            ConnectorSecretBrokerageOptionData.from_application(option) for option in options
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorSecretBrokerageViewResponse, status_code=201)
async def create_connector_secret_brokerage(
    payload: ConnectorSecretBrokerageInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_secret_brokerage_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorSecretBrokerageViewResponse:
    service: ConnectorSecretBrokerageService = request.app.state.secret_brokerage_service
    try:
        record = await service.create(
            actor=subject,
            source_runtime_trust_grant_id=payload.source_runtime_trust_grant_id,
            source_runtime_trust_digest=payload.source_runtime_trust_digest,
            package_digest=payload.package_digest,
            brokerage_profile_id=payload.brokerage_profile_id,
            brokerage_profile_digest=payload.brokerage_profile_digest,
            brokerage_policy_id=payload.brokerage_policy_id,
            brokerage_policy_digest=payload.brokerage_policy_digest,
            purpose=payload.purpose,
            authorization_only_acknowledged=(
                payload.acknowledged_authorization_grants_no_lease_secret_runtime_target_execution_or_deployment
            ),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorSecretBrokerageError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{authorization_id}", response_model=ConnectorSecretBrokerageViewResponse)
async def get_connector_secret_brokerage(
    authorization_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_secret_brokerage_read)],
) -> ConnectorSecretBrokerageViewResponse:
    service: ConnectorSecretBrokerageService = request.app.state.secret_brokerage_service
    try:
        record = await service.get(
            actor=subject,
            authorization_id=authorization_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorSecretBrokerageError as error:
        _raise(error)
    return _response(record, request, response)
