from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.embedding_generation_schemas import (
    OperationalKnowledgeEmbeddingData,
    OperationalKnowledgeEmbeddingInput,
    OperationalKnowledgeEmbeddingResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_embedding_generation_create,
    authorize_operational_knowledge_embedding_generation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.embedding_generation import (
    OperationalKnowledgeEmbeddingGenerationService,
)
from atlas.modules.knowledge.application.embedding_generation_ports import (
    OperationalKnowledgeEmbeddingError,
    OperationalKnowledgeEmbeddingUncertainError,
)
from atlas.modules.knowledge.domain.embedding_generation import (
    OperationalKnowledgeEmbeddingRecord,
)

router = APIRouter(prefix="/knowledge/chunk-sets", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgeEmbeddingError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeEmbeddingUncertainError):
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
        title="Operational knowledge embedding generation unavailable",
        detail=(
            "No chunk content, coordinate, vector, index, retrieval, workflow, or operational "
            "authority was returned. Claimed uncertain embedding attempts are not retried."
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
    record: OperationalKnowledgeEmbeddingRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgeEmbeddingResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return OperationalKnowledgeEmbeddingResponse(
        data=OperationalKnowledgeEmbeddingData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{chunk_set_id}/embedding-sets",
    response_model=OperationalKnowledgeEmbeddingResponse,
    status_code=201,
)
async def create_operational_knowledge_embedding_set(
    chunk_set_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgeEmbeddingInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_embedding_generation_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeEmbeddingResponse:
    service: OperationalKnowledgeEmbeddingGenerationService = (
        request.app.state.operational_knowledge_embedding_generation_service
    )
    try:
        record = await service.create(
            actor=subject,
            chunk_set_id=chunk_set_id,
            chunk_set_digest=payload.chunk_set_digest,
            embedding_policy_id=payload.embedding_policy_id,
            embedding_policy_digest=payload.embedding_policy_digest,
            purpose=payload.purpose,
            protected_boundary_acknowledged=(payload.acknowledged_protected_chunk_boundary),
            immutable_model_profile_acknowledged=(payload.acknowledged_immutable_model_profile),
            no_index_or_operational_authority_acknowledged=(
                payload.acknowledged_no_index_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeEmbeddingError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{chunk_set_id}/embedding-sets/{embedding_set_id}",
    response_model=OperationalKnowledgeEmbeddingResponse,
)
async def get_operational_knowledge_embedding_set(
    chunk_set_id: Annotated[str, SAFE_ID],
    embedding_set_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_embedding_generation_read),
    ],
) -> OperationalKnowledgeEmbeddingResponse:
    service: OperationalKnowledgeEmbeddingGenerationService = (
        request.app.state.operational_knowledge_embedding_generation_service
    )
    try:
        record = await service.get(
            actor=subject,
            embedding_set_id=embedding_set_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if record.chunk_set_id != chunk_set_id:
            raise OperationalKnowledgeEmbeddingError("operational_knowledge_embedding_not_found")
    except OperationalKnowledgeEmbeddingError as error:
        _raise(error)
    return _response(record, request, response)
