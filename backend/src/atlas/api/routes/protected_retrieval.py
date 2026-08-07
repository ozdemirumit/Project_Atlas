from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.protected_retrieval_schemas import (
    OperationalKnowledgeRetrievalInput,
    OperationalKnowledgeRetrievalResponse,
    OperationalKnowledgeRetrievalResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_protected_retrieval_create,
    authorize_operational_knowledge_protected_retrieval_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.protected_retrieval import (
    OperationalKnowledgeProtectedRetrievalService,
)
from atlas.modules.knowledge.application.protected_retrieval_ports import (
    OperationalKnowledgeRetrievalError,
    OperationalKnowledgeRetrievalUncertainError,
)
from atlas.modules.knowledge.domain.protected_retrieval import OperationalKnowledgeRetrievalResult

router = APIRouter(prefix="/knowledge/retrieval-publications", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgeRetrievalError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeRetrievalUncertainError):
        status = 503
    elif code.endswith(("required", "denied", "mfa_required")):
        status = 403
    elif code.endswith(("not_found", "unavailable")):
        status = 404
    elif code.endswith(("invalid", "integrity_failed")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Protected operational knowledge retrieval unavailable",
        detail=(
            "No unauthorized candidate, vector-store internal, model context, workflow, or "
            "operational authority was returned. Retrieval does not invoke a model or tool."
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
    result: OperationalKnowledgeRetrievalResult,
    request: Request,
    response: Response,
) -> OperationalKnowledgeRetrievalResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return OperationalKnowledgeRetrievalResponse(
        data=OperationalKnowledgeRetrievalResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{publication_id}/retrievals",
    response_model=OperationalKnowledgeRetrievalResponse,
    status_code=201,
)
async def create_operational_knowledge_retrieval(
    publication_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgeRetrievalInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_protected_retrieval_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeRetrievalResponse:
    service: OperationalKnowledgeProtectedRetrievalService = (
        request.app.state.operational_knowledge_protected_retrieval_service
    )
    try:
        result = await service.create(
            actor=subject,
            publication_id=publication_id,
            publication_digest=payload.publication_digest,
            retrieval_policy_id=payload.retrieval_policy_id,
            retrieval_policy_digest=payload.retrieval_policy_digest,
            query=payload.query,
            purpose=payload.purpose,
            untrusted_evidence_acknowledged=payload.acknowledged_untrusted_evidence,
            unsafe_instructions_acknowledged=payload.acknowledged_unsafe_instructions,
            no_model_or_operational_authority_acknowledged=(
                payload.acknowledged_no_model_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeRetrievalError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{publication_id}/retrievals/{retrieval_id}",
    response_model=OperationalKnowledgeRetrievalResponse,
)
async def get_operational_knowledge_retrieval(
    publication_id: Annotated[str, SAFE_ID],
    retrieval_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_protected_retrieval_read),
    ],
) -> OperationalKnowledgeRetrievalResponse:
    service: OperationalKnowledgeProtectedRetrievalService = (
        request.app.state.operational_knowledge_protected_retrieval_service
    )
    try:
        result = await service.get(
            actor=subject,
            retrieval_id=retrieval_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.publication_id != publication_id:
            raise OperationalKnowledgeRetrievalError("operational_knowledge_retrieval_not_found")
    except OperationalKnowledgeRetrievalError as error:
        _raise(error)
    return _response(result, request, response)
