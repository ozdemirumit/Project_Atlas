from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.review_finding_schemas import (
    OperationalKnowledgeReviewFindingData,
    OperationalKnowledgeReviewFindingInput,
    OperationalKnowledgeReviewFindingResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_review_finding_create,
    authorize_operational_knowledge_review_finding_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.review_finding import (
    OperationalKnowledgeReviewFindingService,
)
from atlas.modules.knowledge.application.review_finding_ports import (
    OperationalKnowledgeReviewFindingError,
    OperationalKnowledgeReviewFindingUncertainError,
)
from atlas.modules.knowledge.domain.review_finding import (
    OperationalKnowledgeReviewFindingItem,
    OperationalKnowledgeReviewFindingRecord,
)

router = APIRouter(prefix="/knowledge/protected-inspections/leases", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgeReviewFindingError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeReviewFindingUncertainError):
        status = 503
    elif code.endswith(("required", "denied", "human_required")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith(("invalid", "integrity_failed", "too_large")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Operational knowledge review finding unavailable",
        detail=(
            "No finding content, artifact location, review decision, approval, publication, "
            "workflow authority, or operational authority was returned. Claimed uncertain "
            "finding packets are not retried."
        ),
    ) from error


def _lease_secrets(request: Request) -> dict[str, str]:
    secrets: dict[str, str] = {}
    domain = request.cookies.get("atlas_knowledge_inspection_domain")
    security = request.cookies.get("atlas_knowledge_inspection_security")
    if domain:
        secrets["review-track.domain"] = domain
    if security:
        secrets["review-track.security"] = security
    return secrets


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
    record: OperationalKnowledgeReviewFindingRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgeReviewFindingResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return OperationalKnowledgeReviewFindingResponse(
        data=OperationalKnowledgeReviewFindingData.from_record(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{lease_id}/presentations/{presentation_id}/findings",
    response_model=OperationalKnowledgeReviewFindingResponse,
    status_code=201,
)
async def create_operational_knowledge_review_finding(
    lease_id: Annotated[str, SAFE_ID],
    presentation_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgeReviewFindingInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_review_finding_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeReviewFindingResponse:
    service: OperationalKnowledgeReviewFindingService = (
        request.app.state.operational_knowledge_review_finding_service
    )
    try:
        record = await service.create(
            actor=subject,
            source_lease_id=lease_id,
            source_presentation_id=presentation_id,
            source_presentation_digest=payload.source_presentation_digest,
            finding_policy_id=payload.finding_policy_id,
            finding_policy_digest=payload.finding_policy_digest,
            findings=tuple(
                OperationalKnowledgeReviewFindingItem(
                    category_code=item.category_code,
                    severity_code=item.severity_code,
                    summary=item.summary,
                    detail=item.detail,
                )
                for item in payload.findings
            ),
            purpose=payload.purpose,
            evidence_review_acknowledged=payload.acknowledged_evidence_was_reviewed,
            finding_is_not_decision_acknowledged=(
                payload.acknowledged_finding_is_not_a_review_decision
            ),
            browser_session_id=_browser_session_id(request),
            lease_secrets=_lease_secrets(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeReviewFindingError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{lease_id}/presentations/{presentation_id}/findings/{finding_packet_id}",
    response_model=OperationalKnowledgeReviewFindingResponse,
)
async def get_operational_knowledge_review_finding(
    lease_id: Annotated[str, SAFE_ID],
    presentation_id: Annotated[str, SAFE_ID],
    finding_packet_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_review_finding_read),
    ],
) -> OperationalKnowledgeReviewFindingResponse:
    service: OperationalKnowledgeReviewFindingService = (
        request.app.state.operational_knowledge_review_finding_service
    )
    try:
        record = await service.get(
            actor=subject,
            source_lease_id=lease_id,
            source_presentation_id=presentation_id,
            finding_packet_id=finding_packet_id,
            browser_session_id=_browser_session_id(request),
            lease_secrets=_lease_secrets(request),
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeReviewFindingError as error:
        _raise(error)
    return _response(record, request, response)
