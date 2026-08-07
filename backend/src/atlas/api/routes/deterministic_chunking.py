from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.deterministic_chunking_schemas import (
    OperationalKnowledgeChunkingData,
    OperationalKnowledgeChunkingInput,
    OperationalKnowledgeChunkingResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_deterministic_chunking_create,
    authorize_operational_knowledge_deterministic_chunking_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.deterministic_chunking import (
    OperationalKnowledgeDeterministicChunkingService,
)
from atlas.modules.knowledge.application.deterministic_chunking_ports import (
    OperationalKnowledgeChunkingError,
    OperationalKnowledgeChunkingUncertainError,
)
from atlas.modules.knowledge.domain.deterministic_chunking import (
    OperationalKnowledgeChunkingRecord,
)

router = APIRouter(prefix="/knowledge/source-materializations", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgeChunkingError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeChunkingUncertainError):
        status = 503
    elif code.endswith(("required", "denied", "mfa_required")):
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
        title="Operational knowledge deterministic chunking unavailable",
        detail=(
            "No content, coordinate, embedding, retrieval, workflow, or operational authority "
            "was returned. Claimed uncertain chunking attempts are not retried."
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
    record: OperationalKnowledgeChunkingRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgeChunkingResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return OperationalKnowledgeChunkingResponse(
        data=OperationalKnowledgeChunkingData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{materialization_id}/chunk-sets",
    response_model=OperationalKnowledgeChunkingResponse,
    status_code=201,
)
async def create_operational_knowledge_chunk_set(
    materialization_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgeChunkingInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_deterministic_chunking_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeChunkingResponse:
    service: OperationalKnowledgeDeterministicChunkingService = (
        request.app.state.operational_knowledge_deterministic_chunking_service
    )
    try:
        record = await service.create(
            actor=subject,
            materialization_id=materialization_id,
            materialization_digest=payload.source_materialization_digest,
            chunking_policy_id=payload.chunking_policy_id,
            chunking_policy_digest=payload.chunking_policy_digest,
            purpose=payload.purpose,
            protected_boundary_acknowledged=(payload.acknowledged_protected_content_boundary),
            immutable_profile_acknowledged=(payload.acknowledged_immutable_chunking_profile),
            no_embedding_or_operational_authority_acknowledged=(
                payload.acknowledged_no_embedding_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeChunkingError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{materialization_id}/chunk-sets/{chunk_set_id}",
    response_model=OperationalKnowledgeChunkingResponse,
)
async def get_operational_knowledge_chunk_set(
    materialization_id: Annotated[str, SAFE_ID],
    chunk_set_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_deterministic_chunking_read),
    ],
) -> OperationalKnowledgeChunkingResponse:
    service: OperationalKnowledgeDeterministicChunkingService = (
        request.app.state.operational_knowledge_deterministic_chunking_service
    )
    try:
        record = await service.get(
            actor=subject,
            chunk_set_id=chunk_set_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if record.materialization_id != materialization_id:
            raise OperationalKnowledgeChunkingError("operational_knowledge_chunking_not_found")
    except OperationalKnowledgeChunkingError as error:
        _raise(error)
    return _response(record, request, response)
