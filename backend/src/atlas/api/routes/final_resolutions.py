from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.final_resolution_schemas import (
    OperationalKnowledgeFinalResolutionData,
    OperationalKnowledgeFinalResolutionInput,
    OperationalKnowledgeFinalResolutionResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_final_resolution_create,
    authorize_operational_knowledge_final_resolution_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.final_resolution import (
    OperationalKnowledgeFinalResolutionService,
)
from atlas.modules.knowledge.application.final_resolution_ports import (
    OperationalKnowledgeFinalResolutionError,
    OperationalKnowledgeFinalResolutionUncertainError,
)
from atlas.modules.knowledge.domain.final_resolution import (
    OperationalKnowledgeFinalResolutionRecord,
)

router = APIRouter(prefix="/knowledge/review-requests", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgeFinalResolutionError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeFinalResolutionUncertainError):
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
        title="Operational knowledge final resolution unavailable",
        detail=(
            "No content, publication, retrieval, workflow, or operational authority was returned. "
            "Claimed uncertain resolutions are not retried."
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
    record: OperationalKnowledgeFinalResolutionRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgeFinalResolutionResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return OperationalKnowledgeFinalResolutionResponse(
        data=OperationalKnowledgeFinalResolutionData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{review_request_id}/final-resolutions",
    response_model=OperationalKnowledgeFinalResolutionResponse,
    status_code=201,
)
async def create_operational_knowledge_final_resolution(
    review_request_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgeFinalResolutionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_final_resolution_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeFinalResolutionResponse:
    service: OperationalKnowledgeFinalResolutionService = (
        request.app.state.operational_knowledge_final_resolution_service
    )
    try:
        record = await service.create(
            actor=subject,
            review_request_id=review_request_id,
            review_request_digest=payload.review_request_digest,
            decision_ids=payload.decision_ids,
            decision_digests=payload.decision_digests,
            disposition_code=payload.disposition_code,
            basis_codes=payload.basis_codes,
            resolution_policy_id=payload.resolution_policy_id,
            resolution_policy_digest=payload.resolution_policy_digest,
            purpose=payload.purpose,
            immutable_generation_acknowledged=payload.acknowledged_immutable_review_generation,
            publication_readiness_only_acknowledged=(
                payload.acknowledged_publication_readiness_only
            ),
            no_operational_authority_acknowledged=payload.acknowledged_no_operational_authority,
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeFinalResolutionError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{review_request_id}/final-resolutions/{resolution_id}",
    response_model=OperationalKnowledgeFinalResolutionResponse,
)
async def get_operational_knowledge_final_resolution(
    review_request_id: Annotated[str, SAFE_ID],
    resolution_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_final_resolution_read),
    ],
) -> OperationalKnowledgeFinalResolutionResponse:
    service: OperationalKnowledgeFinalResolutionService = (
        request.app.state.operational_knowledge_final_resolution_service
    )
    try:
        record = await service.get(
            actor=subject,
            resolution_id=resolution_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if record.review_request_id != review_request_id:
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_not_found"
            )
    except OperationalKnowledgeFinalResolutionError as error:
        _raise(error)
    return _response(record, request, response)
