from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.index_staging_validation_schemas import (
    OperationalKnowledgeIndexData,
    OperationalKnowledgeIndexInput,
    OperationalKnowledgeIndexResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_index_staging_create,
    authorize_operational_knowledge_index_staging_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.index_staging_validation import (
    OperationalKnowledgeIndexStagingValidationService,
)
from atlas.modules.knowledge.application.index_staging_validation_ports import (
    OperationalKnowledgeIndexError,
    OperationalKnowledgeIndexUncertainError,
)
from atlas.modules.knowledge.domain.index_staging_validation import (
    OperationalKnowledgeIndexRecord,
)

router = APIRouter(prefix="/knowledge/embedding-sets", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgeIndexError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeIndexUncertainError):
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
        title="Operational knowledge index staging unavailable",
        detail=(
            "No content, coordinate, vector, collection, point, payload, retrieval, workflow, "
            "or operational authority was returned. Claimed uncertain staging attempts are not "
            "retried."
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
    record: OperationalKnowledgeIndexRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgeIndexResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return OperationalKnowledgeIndexResponse(
        data=OperationalKnowledgeIndexData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{embedding_set_id}/index-stages",
    response_model=OperationalKnowledgeIndexResponse,
    status_code=201,
)
async def create_operational_knowledge_index_stage(
    embedding_set_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgeIndexInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_index_staging_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeIndexResponse:
    service: OperationalKnowledgeIndexStagingValidationService = (
        request.app.state.operational_knowledge_index_staging_validation_service
    )
    try:
        record = await service.create(
            actor=subject,
            embedding_set_id=embedding_set_id,
            embedding_set_digest=payload.embedding_set_digest,
            index_policy_id=payload.index_policy_id,
            index_policy_digest=payload.index_policy_digest,
            purpose=payload.purpose,
            protected_vector_boundary_acknowledged=(payload.acknowledged_protected_vector_boundary),
            inactive_projection_acknowledged=payload.acknowledged_inactive_projection,
            no_publication_or_operational_authority_acknowledged=(
                payload.acknowledged_no_publication_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeIndexError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{embedding_set_id}/index-stages/{index_staging_id}",
    response_model=OperationalKnowledgeIndexResponse,
)
async def get_operational_knowledge_index_stage(
    embedding_set_id: Annotated[str, SAFE_ID],
    index_staging_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_index_staging_read),
    ],
) -> OperationalKnowledgeIndexResponse:
    service: OperationalKnowledgeIndexStagingValidationService = (
        request.app.state.operational_knowledge_index_staging_validation_service
    )
    try:
        record = await service.get(
            actor=subject,
            index_staging_id=index_staging_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if record.embedding_set_id != embedding_set_id:
            raise OperationalKnowledgeIndexError("operational_knowledge_index_not_found")
    except OperationalKnowledgeIndexError as error:
        _raise(error)
    return _response(record, request, response)
