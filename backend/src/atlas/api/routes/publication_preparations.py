from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.publication_preparation_schemas import (
    OperationalKnowledgePublicationPreparationData,
    OperationalKnowledgePublicationPreparationInput,
    OperationalKnowledgePublicationPreparationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_publication_preparation_create,
    authorize_operational_knowledge_publication_preparation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.publication_preparation import (
    OperationalKnowledgePublicationPreparationService,
)
from atlas.modules.knowledge.application.publication_preparation_ports import (
    OperationalKnowledgePublicationPreparationError,
    OperationalKnowledgePublicationPreparationUncertainError,
)
from atlas.modules.knowledge.domain.publication_preparation import (
    OperationalKnowledgePublicationPreparationRecord,
)

router = APIRouter(prefix="/knowledge/final-resolutions", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgePublicationPreparationError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgePublicationPreparationUncertainError):
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
        title="Operational knowledge publication preparation unavailable",
        detail=(
            "No content, processing, publication, retrieval, workflow, or operational authority "
            "was returned. Claimed uncertain preparations are not retried."
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
    record: OperationalKnowledgePublicationPreparationRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgePublicationPreparationResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return OperationalKnowledgePublicationPreparationResponse(
        data=OperationalKnowledgePublicationPreparationData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{resolution_id}/publication-preparations",
    response_model=OperationalKnowledgePublicationPreparationResponse,
    status_code=201,
)
async def create_operational_knowledge_publication_preparation(
    resolution_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgePublicationPreparationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_publication_preparation_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgePublicationPreparationResponse:
    service: OperationalKnowledgePublicationPreparationService = (
        request.app.state.operational_knowledge_publication_preparation_service
    )
    try:
        record = await service.create(
            actor=subject,
            resolution_id=resolution_id,
            resolution_digest=payload.final_resolution_digest,
            preparation_policy_id=payload.preparation_policy_id,
            preparation_policy_digest=payload.preparation_policy_digest,
            purpose=payload.purpose,
            immutable_generation_acknowledged=(payload.acknowledged_immutable_approved_generation),
            metadata_only_acknowledged=payload.acknowledged_metadata_only_preparation,
            no_processing_or_operational_authority_acknowledged=(
                payload.acknowledged_no_processing_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgePublicationPreparationError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{resolution_id}/publication-preparations/{preparation_id}",
    response_model=OperationalKnowledgePublicationPreparationResponse,
)
async def get_operational_knowledge_publication_preparation(
    resolution_id: Annotated[str, SAFE_ID],
    preparation_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_publication_preparation_read),
    ],
) -> OperationalKnowledgePublicationPreparationResponse:
    service: OperationalKnowledgePublicationPreparationService = (
        request.app.state.operational_knowledge_publication_preparation_service
    )
    try:
        record = await service.get(
            actor=subject,
            preparation_id=preparation_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if record.resolution_id != resolution_id:
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_not_found"
            )
    except OperationalKnowledgePublicationPreparationError as error:
        _raise(error)
    return _response(record, request, response)
