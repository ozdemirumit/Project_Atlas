from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.retrieval_index_publication_schemas import (
    OperationalKnowledgeRetrievalPublicationData,
    OperationalKnowledgeRetrievalPublicationInput,
    OperationalKnowledgeRetrievalPublicationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_retrieval_publication_create,
    authorize_operational_knowledge_retrieval_publication_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.retrieval_index_publication import (
    OperationalKnowledgeRetrievalIndexPublicationService,
)
from atlas.modules.knowledge.application.retrieval_index_publication_ports import (
    OperationalKnowledgeRetrievalPublicationError,
    OperationalKnowledgeRetrievalPublicationUncertainError,
)
from atlas.modules.knowledge.domain.retrieval_index_publication import (
    OperationalKnowledgeRetrievalPublicationRecord,
)

router = APIRouter(prefix="/knowledge/index-stages", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgeRetrievalPublicationError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeRetrievalPublicationUncertainError):
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
        title="Operational knowledge retrieval publication unavailable",
        detail=(
            "No content, coordinate, vector, collection, alias, point, payload, query, model "
            "context, workflow, or operational authority was returned. Claimed uncertain "
            "publication attempts are not retried."
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
    record: OperationalKnowledgeRetrievalPublicationRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgeRetrievalPublicationResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return OperationalKnowledgeRetrievalPublicationResponse(
        data=OperationalKnowledgeRetrievalPublicationData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{index_staging_id}/publications",
    response_model=OperationalKnowledgeRetrievalPublicationResponse,
    status_code=201,
)
async def create_operational_knowledge_retrieval_publication(
    index_staging_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgeRetrievalPublicationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_retrieval_publication_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeRetrievalPublicationResponse:
    service: OperationalKnowledgeRetrievalIndexPublicationService = (
        request.app.state.operational_knowledge_retrieval_index_publication_service
    )
    try:
        record = await service.create(
            actor=subject,
            index_staging_id=index_staging_id,
            index_staging_digest=payload.index_staging_digest,
            publication_policy_id=payload.publication_policy_id,
            publication_policy_digest=payload.publication_policy_digest,
            purpose=payload.purpose,
            policy_filtered_visibility_acknowledged=(
                payload.acknowledged_policy_filtered_visibility
            ),
            no_vector_store_disclosure_acknowledged=(
                payload.acknowledged_no_vector_store_disclosure
            ),
            no_context_or_operational_authority_acknowledged=(
                payload.acknowledged_no_context_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeRetrievalPublicationError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{index_staging_id}/publications/{publication_id}",
    response_model=OperationalKnowledgeRetrievalPublicationResponse,
)
async def get_operational_knowledge_retrieval_publication(
    index_staging_id: Annotated[str, SAFE_ID],
    publication_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_retrieval_publication_read),
    ],
) -> OperationalKnowledgeRetrievalPublicationResponse:
    service: OperationalKnowledgeRetrievalIndexPublicationService = (
        request.app.state.operational_knowledge_retrieval_index_publication_service
    )
    try:
        record = await service.get(
            actor=subject,
            publication_id=publication_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if record.index_staging_id != index_staging_id:
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_not_found"
            )
    except OperationalKnowledgeRetrievalPublicationError as error:
        _raise(error)
    return _response(record, request, response)
