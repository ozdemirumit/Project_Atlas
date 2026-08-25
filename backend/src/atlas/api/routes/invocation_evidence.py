from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.invocation_evidence_schemas import (
    ConnectorInvocationEvidenceData,
    ConnectorInvocationEvidenceInput,
    ConnectorInvocationEvidenceInventoryResponse,
    ConnectorInvocationEvidenceOptionData,
    ConnectorInvocationEvidenceOptionsResponse,
    ConnectorInvocationEvidenceResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_invocation_evidence_create,
    authorize_connector_invocation_evidence_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.invocation_evidence import (
    ConnectorInvocationEvidenceService,
)
from atlas.modules.connectors.application.invocation_evidence_ports import (
    ConnectorInvocationEvidenceError,
    ConnectorInvocationEvidenceUncertainError,
)
from atlas.modules.connectors.domain.invocation_evidence import (
    ConnectorInvocationEvidenceRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/invocation-evidence", tags=["connectors"])
STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorInvocationEvidenceError) -> NoReturn:
    code = str(error)
    if isinstance(error, ConnectorInvocationEvidenceUncertainError):
        status = 503
    elif code.endswith(("required", "denied", "separation_required")):
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
        title="Connector invocation evidence unavailable",
        detail=(
            "Evidence ingestion did not publish knowledge or grant operational authority. "
            "Uncertain claimed attempts are not retried automatically."
        ),
    ) from error


def _response(
    record: ConnectorInvocationEvidenceRecord,
    request: Request,
    response: Response,
) -> ConnectorInvocationEvidenceResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorInvocationEvidenceResponse(
        data=ConnectorInvocationEvidenceData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("", response_model=ConnectorInvocationEvidenceInventoryResponse)
async def list_connector_invocation_evidence(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_invocation_evidence_read)
    ],
    source_invocation_id: Annotated[str | None, Query(pattern=STABLE_ID)] = None,
) -> ConnectorInvocationEvidenceInventoryResponse:
    service: ConnectorInvocationEvidenceService = request.app.state.invocation_evidence_service
    try:
        records = await service.list_evidence(
            actor=subject,
            source_invocation_id=source_invocation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInvocationEvidenceError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorInvocationEvidenceInventoryResponse(
        data=tuple(ConnectorInvocationEvidenceData.from_domain(record) for record in records),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/options", response_model=ConnectorInvocationEvidenceOptionsResponse)
async def list_connector_invocation_evidence_options(
    source_invocation_id: Annotated[str, Query(pattern=STABLE_ID)],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_invocation_evidence_read)
    ],
) -> ConnectorInvocationEvidenceOptionsResponse:
    service: ConnectorInvocationEvidenceService = request.app.state.invocation_evidence_service
    try:
        options = await service.list_options(
            actor=subject,
            source_invocation_id=source_invocation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInvocationEvidenceError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorInvocationEvidenceOptionsResponse(
        data=tuple(
            ConnectorInvocationEvidenceOptionData.from_application(option) for option in options
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorInvocationEvidenceResponse, status_code=201)
async def create_connector_invocation_evidence(
    payload: ConnectorInvocationEvidenceInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_invocation_evidence_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorInvocationEvidenceResponse:
    service: ConnectorInvocationEvidenceService = request.app.state.invocation_evidence_service
    try:
        record = await service.create(
            actor=subject,
            source_invocation_id=payload.source_invocation_id,
            source_invocation_digest=payload.source_invocation_digest,
            ingestion_policy_id=payload.ingestion_policy_id,
            ingestion_policy_digest=payload.ingestion_policy_digest,
            purpose=payload.purpose,
            one_way_ingestion_acknowledged=(
                payload.acknowledged_ingestion_is_one_way_and_does_not_publish_knowledge_or_grant_authority
            ),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInvocationEvidenceError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{ingestion_id}", response_model=ConnectorInvocationEvidenceResponse)
async def get_connector_invocation_evidence(
    ingestion_id: Annotated[str, Path(pattern=STABLE_ID)],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_invocation_evidence_read)
    ],
) -> ConnectorInvocationEvidenceResponse:
    service: ConnectorInvocationEvidenceService = request.app.state.invocation_evidence_service
    try:
        record = await service.get(
            actor=subject,
            ingestion_id=ingestion_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInvocationEvidenceError as error:
        _raise(error)
    return _response(record, request, response)
