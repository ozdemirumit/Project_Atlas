from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.package_approval_schemas import (
    ConnectorPackageApprovalData,
    ConnectorPackageApprovalDecisionInput,
    ConnectorPackageApprovalRequestInput,
    ConnectorPackageApprovalResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_approval_create,
    authorize_connector_package_approval_decide,
    authorize_connector_package_approval_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.package_approval import PackageApprovalService
from atlas.modules.connectors.application.package_approval_ports import PackageApprovalError
from atlas.modules.connectors.domain.package_approval import (
    ConnectorPackageApprovalRecord,
    PackageApprovalOutcome,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-approval-requests", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: PackageApprovalError) -> NoReturn:
    if error.code.endswith(("human_required", "separation_required")):
        status = 403
    elif error.code.endswith("not_found"):
        status = 404
    elif error.code.endswith(("invalid", "required")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="Connector package approval unavailable",
        detail="The governed connector package approval operation could not be completed.",
    ) from error


def _response(
    record: ConnectorPackageApprovalRecord, request: Request, response: Response
) -> ConnectorPackageApprovalResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageApprovalResponse(
        data=ConnectorPackageApprovalData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPackageApprovalResponse, status_code=201)
async def create_connector_package_approval_request(
    payload: ConnectorPackageApprovalRequestInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_approval_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageApprovalResponse:
    service: PackageApprovalService = request.app.state.package_approval_service
    try:
        record = await service.create_request(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageApprovalError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{request_id}", response_model=ConnectorPackageApprovalResponse)
async def get_connector_package_approval_request(
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_package_approval_read)],
) -> ConnectorPackageApprovalResponse:
    service: PackageApprovalService = request.app.state.package_approval_service
    try:
        record = await service.get(
            actor=subject,
            request_id=request_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageApprovalError as error:
        _raise(error)
    return _response(record, request, response)


@router.post("/{request_id}/decisions", response_model=ConnectorPackageApprovalResponse)
async def decide_connector_package_approval_request(
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ConnectorPackageApprovalDecisionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_approval_decide)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageApprovalResponse:
    service: PackageApprovalService = request.app.state.package_approval_service
    try:
        data = payload.model_dump(exclude={"schema_version"})
        data["outcome"] = PackageApprovalOutcome(str(data["outcome"]))
        record = await service.decide(
            actor=subject,
            request_id=request_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **data,
        )
    except PackageApprovalError as error:
        _raise(error)
    return _response(record, request, response)
