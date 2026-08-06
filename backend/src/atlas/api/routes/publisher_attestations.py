from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.publisher_attestation_schemas import (
    ConnectorPublisherAttestationData,
    ConnectorPublisherAttestationInput,
    ConnectorPublisherAttestationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_publisher_attestation_create,
    authorize_connector_publisher_attestation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.publisher_attestation import PublisherAttestationService
from atlas.modules.connectors.application.publisher_attestation_ports import (
    PublisherAttestationError,
)
from atlas.modules.connectors.domain.publisher_attestation import (
    ConnectorPublisherAttestationReport,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/publisher-attestations", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: PublisherAttestationError) -> NoReturn:
    if error.code.endswith(("mfa_required", "separation_required")):
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
        title="Connector publisher attestation unavailable",
        detail="The governed connector publisher attestation operation could not be completed.",
    ) from error


def _response(
    report: ConnectorPublisherAttestationReport, request: Request, response: Response
) -> ConnectorPublisherAttestationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPublisherAttestationResponse(
        data=ConnectorPublisherAttestationData.from_domain(report),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPublisherAttestationResponse, status_code=201)
async def create_connector_publisher_attestation(
    payload: ConnectorPublisherAttestationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_publisher_attestation_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPublisherAttestationResponse:
    service: PublisherAttestationService = request.app.state.publisher_attestation_service
    try:
        report = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PublisherAttestationError as error:
        _raise(error)
    return _response(report, request, response)


@router.get("/{report_id}", response_model=ConnectorPublisherAttestationResponse)
async def get_connector_publisher_attestation(
    report_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_publisher_attestation_read)
    ],
) -> ConnectorPublisherAttestationResponse:
    service: PublisherAttestationService = request.app.state.publisher_attestation_service
    try:
        report = await service.get(
            actor=subject,
            report_id=report_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PublisherAttestationError as error:
        _raise(error)
    return _response(report, request, response)
