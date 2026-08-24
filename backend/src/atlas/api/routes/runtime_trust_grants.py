from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.runtime_trust_schemas import (
    ConnectorRuntimeTrustInput,
    ConnectorRuntimeTrustInventoryData,
    ConnectorRuntimeTrustInventoryResponse,
    ConnectorRuntimeTrustOptionData,
    ConnectorRuntimeTrustOptionsResponse,
    ConnectorRuntimeTrustViewResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_runtime_trust_create,
    authorize_connector_runtime_trust_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.runtime_trust import ConnectorRuntimeTrustService
from atlas.modules.connectors.application.runtime_trust_ports import ConnectorRuntimeTrustError
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/runtime-trust-grants", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorRuntimeTrustError) -> NoReturn:
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
        title="Connector runtime trust unavailable",
        detail="The governed connector runtime trust grant could not be completed.",
    ) from error


def _response(
    record: ConnectorRuntimeTrustGrantRecord, request: Request, response: Response
) -> ConnectorRuntimeTrustViewResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorRuntimeTrustViewResponse(
        data=ConnectorRuntimeTrustInventoryData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("", response_model=ConnectorRuntimeTrustInventoryResponse)
async def list_connector_runtime_trust_grants(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_runtime_trust_read)],
    source_enablement_id: Annotated[
        str | None, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    ] = None,
) -> ConnectorRuntimeTrustInventoryResponse:
    service: ConnectorRuntimeTrustService = request.app.state.runtime_trust_service
    try:
        records = await service.list_grants(
            actor=subject,
            source_enablement_id=source_enablement_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorRuntimeTrustError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorRuntimeTrustInventoryResponse(
        data=tuple(ConnectorRuntimeTrustInventoryData.from_domain(record) for record in records),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/options", response_model=ConnectorRuntimeTrustOptionsResponse)
async def list_connector_runtime_trust_options(
    source_enablement_id: Annotated[str, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_runtime_trust_read)],
) -> ConnectorRuntimeTrustOptionsResponse:
    service: ConnectorRuntimeTrustService = request.app.state.runtime_trust_service
    try:
        options = await service.list_options(
            actor=subject,
            source_enablement_id=source_enablement_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorRuntimeTrustError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorRuntimeTrustOptionsResponse(
        data=tuple(ConnectorRuntimeTrustOptionData.from_application(option) for option in options),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorRuntimeTrustViewResponse, status_code=201)
async def create_connector_runtime_trust(
    payload: ConnectorRuntimeTrustInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_runtime_trust_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorRuntimeTrustViewResponse:
    service: ConnectorRuntimeTrustService = request.app.state.runtime_trust_service
    try:
        record = await service.create(
            actor=subject,
            source_enablement_id=payload.source_enablement_id,
            source_enablement_digest=payload.source_enablement_digest,
            package_digest=payload.package_digest,
            runtime_profile_id=payload.runtime_profile_id,
            runtime_profile_digest=payload.runtime_profile_digest,
            trust_policy_id=payload.trust_policy_id,
            trust_policy_digest=payload.trust_policy_digest,
            purpose=payload.purpose,
            boundary_only_acknowledged=(
                payload.acknowledged_trust_grants_no_runtime_start_secret_target_execution_or_deployment_authority
            ),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorRuntimeTrustError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{grant_id}", response_model=ConnectorRuntimeTrustViewResponse)
async def get_connector_runtime_trust(
    grant_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_runtime_trust_read)],
) -> ConnectorRuntimeTrustViewResponse:
    service: ConnectorRuntimeTrustService = request.app.state.runtime_trust_service
    try:
        record = await service.get(
            actor=subject,
            grant_id=grant_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorRuntimeTrustError as error:
        _raise(error)
    return _response(record, request, response)
