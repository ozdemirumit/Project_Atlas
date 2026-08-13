from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.recommendation_human_review_finding_schemas import (
    RecommendationHumanReviewFindingData,
    RecommendationHumanReviewFindingInput,
    RecommendationHumanReviewFindingResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_recommendation_human_review_finding_create,
    authorize_recommendation_human_review_finding_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.human_review_finding import (
    RecommendationHumanReviewFindingService,
)
from atlas.modules.recommendations.application.human_review_finding_ports import (
    RecommendationHumanReviewFindingError,
    RecommendationHumanReviewFindingUncertainError,
)
from atlas.modules.recommendations.domain.human_review_finding import (
    RecommendationHumanReviewFindingItem,
    RecommendationHumanReviewFindingRecord,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: RecommendationHumanReviewFindingError) -> NoReturn:
    code = str(error)
    if isinstance(error, RecommendationHumanReviewFindingUncertainError):
        status = 503
    elif code.endswith(("required", "denied")):
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
        title="Recommendation human review finding unavailable",
        detail=(
            "No finding content, artifact location, review decision, approval, publication, "
            "workflow authority, or operational authority was returned. Claimed uncertain "
            "finding packets are not retried."
        ),
    ) from error


def _lease_secrets(request: Request) -> dict[str, str]:
    secrets: dict[str, str] = {}
    technical = request.cookies.get("atlas_recommendation_inspection_technical")
    service_impact = request.cookies.get("atlas_recommendation_inspection_service_impact")
    if technical:
        secrets["review-track.technical"] = technical
    if service_impact:
        secrets["review-track.service-impact"] = service_impact
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
    record: RecommendationHumanReviewFindingRecord,
    request: Request,
    response: Response,
) -> RecommendationHumanReviewFindingResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return RecommendationHumanReviewFindingResponse(
        data=RecommendationHumanReviewFindingData.from_record(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{recommendation_id}/protected-inspections/leases/{lease_id}/presentations/{presentation_id}/findings",
    response_model=RecommendationHumanReviewFindingResponse,
    status_code=201,
)
async def create_recommendation_human_review_finding(
    recommendation_id: Annotated[str, SAFE_ID],
    lease_id: Annotated[str, SAFE_ID],
    presentation_id: Annotated[str, SAFE_ID],
    payload: RecommendationHumanReviewFindingInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_recommendation_human_review_finding_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> RecommendationHumanReviewFindingResponse:
    service: RecommendationHumanReviewFindingService = (
        request.app.state.recommendation_human_review_finding_service
    )
    try:
        record = await service.create(
            actor=subject,
            recommendation_id=recommendation_id,
            source_lease_id=lease_id,
            source_presentation_id=presentation_id,
            source_presentation_digest=payload.source_presentation_digest,
            finding_policy_id=payload.finding_policy_id,
            finding_policy_digest=payload.finding_policy_digest,
            findings=tuple(
                RecommendationHumanReviewFindingItem(
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
    except RecommendationHumanReviewFindingError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{recommendation_id}/protected-inspections/leases/{lease_id}/presentations/{presentation_id}/findings/{finding_packet_id}",
    response_model=RecommendationHumanReviewFindingResponse,
)
async def get_recommendation_human_review_finding(
    recommendation_id: Annotated[str, SAFE_ID],
    lease_id: Annotated[str, SAFE_ID],
    presentation_id: Annotated[str, SAFE_ID],
    finding_packet_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_recommendation_human_review_finding_read),
    ],
) -> RecommendationHumanReviewFindingResponse:
    service: RecommendationHumanReviewFindingService = (
        request.app.state.recommendation_human_review_finding_service
    )
    try:
        record = await service.get(
            actor=subject,
            recommendation_id=recommendation_id,
            source_lease_id=lease_id,
            source_presentation_id=presentation_id,
            finding_packet_id=finding_packet_id,
            browser_session_id=_browser_session_id(request),
            lease_secrets=_lease_secrets(request),
            correlation_id=str(request.state.correlation_id),
        )
    except RecommendationHumanReviewFindingError as error:
        _raise(error)
    return _response(record, request, response)
