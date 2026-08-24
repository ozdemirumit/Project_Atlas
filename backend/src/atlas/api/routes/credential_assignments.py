from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.credential_assignment_schemas import (
    ConnectorCredentialAssignmentData,
    ConnectorCredentialAssignmentInput,
    ConnectorCredentialAssignmentInventoryData,
    ConnectorCredentialAssignmentInventoryResponse,
    ConnectorCredentialAssignmentOptionData,
    ConnectorCredentialAssignmentOptionsResponse,
    ConnectorCredentialAssignmentResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_credential_assignment_create,
    authorize_connector_credential_assignment_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.credential_assignment import (
    ConnectorCredentialAssignmentService,
)
from atlas.modules.connectors.application.credential_assignment_ports import (
    ConnectorCredentialAssignmentError,
)
from atlas.modules.connectors.domain.credential_assignment import (
    ConnectorCredentialAssignmentRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/credential-assignments", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorCredentialAssignmentError) -> NoReturn:
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
        title="Connector credential assignment unavailable",
        detail="The governed connector credential assignment could not be completed.",
    ) from error


def _response(
    record: ConnectorCredentialAssignmentRecord, request: Request, response: Response
) -> ConnectorCredentialAssignmentResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorCredentialAssignmentResponse(
        data=ConnectorCredentialAssignmentData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("", response_model=ConnectorCredentialAssignmentInventoryResponse)
async def list_connector_credential_assignments(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_credential_assignment_read)
    ],
    source_target_binding_id: Annotated[
        str | None, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    ] = None,
) -> ConnectorCredentialAssignmentInventoryResponse:
    service: ConnectorCredentialAssignmentService = request.app.state.credential_assignment_service
    try:
        assignments = await service.list_assignments(
            actor=subject,
            source_target_binding_id=source_target_binding_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorCredentialAssignmentError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorCredentialAssignmentInventoryResponse(
        data=tuple(
            ConnectorCredentialAssignmentInventoryData.from_domain(item) for item in assignments
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/options", response_model=ConnectorCredentialAssignmentOptionsResponse)
async def list_connector_credential_assignment_options(
    source_target_binding_id: Annotated[str, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_credential_assignment_read)
    ],
) -> ConnectorCredentialAssignmentOptionsResponse:
    service: ConnectorCredentialAssignmentService = request.app.state.credential_assignment_service
    try:
        options = await service.list_options(
            actor=subject,
            source_target_binding_id=source_target_binding_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorCredentialAssignmentError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorCredentialAssignmentOptionsResponse(
        data=tuple(
            ConnectorCredentialAssignmentOptionData.from_application(item) for item in options
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorCredentialAssignmentResponse, status_code=201)
async def create_connector_credential_assignment(
    payload: ConnectorCredentialAssignmentInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_credential_assignment_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorCredentialAssignmentResponse:
    service: ConnectorCredentialAssignmentService = request.app.state.credential_assignment_service
    try:
        record = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorCredentialAssignmentError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{assignment_id}", response_model=ConnectorCredentialAssignmentResponse)
async def get_connector_credential_assignment(
    assignment_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_credential_assignment_read)
    ],
) -> ConnectorCredentialAssignmentResponse:
    service: ConnectorCredentialAssignmentService = request.app.state.credential_assignment_service
    try:
        record = await service.get(
            actor=subject,
            assignment_id=assignment_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorCredentialAssignmentError as error:
        _raise(error)
    return _response(record, request, response)
