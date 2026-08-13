from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_source_materialization_create,
    authorize_operational_knowledge_source_materialization_read,
    browser_session_subject,
)
from atlas.api.source_materialization_schemas import (
    OperationalKnowledgeSourceMaterializationData,
    OperationalKnowledgeSourceMaterializationInput,
    OperationalKnowledgeSourceMaterializationResponse,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.source_materialization import (
    OperationalKnowledgeSourceMaterializationService,
)
from atlas.modules.knowledge.application.source_materialization_ports import (
    OperationalKnowledgeSourceMaterializationError,
    OperationalKnowledgeSourceMaterializationUncertainError,
)
from atlas.modules.knowledge.domain.source_materialization import (
    OperationalKnowledgeSourceMaterializationRecord,
)

router = APIRouter(prefix="/knowledge/publication-preparations", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgeSourceMaterializationError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeSourceMaterializationUncertainError):
        status = 503
    elif code.endswith(("required", "denied")):
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
        title="Operational knowledge source materialization unavailable",
        detail=(
            "No content, coordinate, chunking, retrieval, workflow, or operational authority "
            "was returned. Claimed uncertain materializations are not retried."
        ),
    ) from error


def _browser_session_id(request: Request) -> str:
    value = getattr(request.state, "authenticated_session_id", None)
    if not isinstance(value, str):
        raise AtlasError(
            status=401,
            code="authentication_required",
            title="Authentication required",
            detail="A browser-bound authenticated identity is required.",
        )
    return value


def _response(
    record: OperationalKnowledgeSourceMaterializationRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgeSourceMaterializationResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return OperationalKnowledgeSourceMaterializationResponse(
        data=OperationalKnowledgeSourceMaterializationData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{preparation_id}/source-materializations",
    response_model=OperationalKnowledgeSourceMaterializationResponse,
    status_code=201,
)
async def create_operational_knowledge_source_materialization(
    preparation_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgeSourceMaterializationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_source_materialization_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeSourceMaterializationResponse:
    service: OperationalKnowledgeSourceMaterializationService = (
        request.app.state.operational_knowledge_source_materialization_service
    )
    try:
        record = await service.create(
            actor=subject,
            preparation_id=preparation_id,
            preparation_digest=payload.publication_preparation_digest,
            materialization_policy_id=payload.materialization_policy_id,
            materialization_policy_digest=payload.materialization_policy_digest,
            purpose=payload.purpose,
            immutable_source_acknowledged=payload.acknowledged_immutable_approved_source,
            protected_boundary_acknowledged=payload.acknowledged_protected_content_boundary,
            no_chunking_or_operational_authority_acknowledged=(
                payload.acknowledged_no_chunking_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeSourceMaterializationError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{preparation_id}/source-materializations/{materialization_id}",
    response_model=OperationalKnowledgeSourceMaterializationResponse,
)
async def get_operational_knowledge_source_materialization(
    preparation_id: Annotated[str, SAFE_ID],
    materialization_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_source_materialization_read),
    ],
) -> OperationalKnowledgeSourceMaterializationResponse:
    service: OperationalKnowledgeSourceMaterializationService = (
        request.app.state.operational_knowledge_source_materialization_service
    )
    try:
        record = await service.get(
            actor=subject,
            materialization_id=materialization_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if record.preparation_id != preparation_id:
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_not_found"
            )
    except OperationalKnowledgeSourceMaterializationError as error:
        _raise(error)
    return _response(record, request, response)
