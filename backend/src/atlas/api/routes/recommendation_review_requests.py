from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.recommendation_review_request_schemas import (
    RecommendationReviewRequestInput,
    RecommendationReviewRequestResponse,
    RecommendationReviewRequestResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_recommendation_review_request_create,
    authorize_recommendation_review_request_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.review_request import (
    GovernedRecommendationReviewRequestService,
)
from atlas.modules.recommendations.application.review_request_ports import (
    RecommendationReviewRequestError,
    RecommendationReviewRequestUncertainError,
)
from atlas.modules.recommendations.domain.review_request import (
    RecommendationReviewRequestResult,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: RecommendationReviewRequestError) -> NoReturn:
    code = str(error)
    status = (
        503
        if isinstance(error, RecommendationReviewRequestUncertainError)
        else 403
        if code.endswith(("required", "denied", "mfa_required"))
        else 404
        if code.endswith(("not_found", "unavailable"))
        else 422
        if code.endswith(("invalid", "integrity_failed"))
        else 409
    )
    raise AtlasError(
        status=status,
        code=code,
        title="Recommendation human-review request unavailable",
        detail=(
            "No reviewer assignment, content inspection, human decision, approval, workflow, "
            "ITSM record, execution authority, deployment authority, or infrastructure mutation "
            "was returned."
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
    result: RecommendationReviewRequestResult,
    request: Request,
    response: Response,
) -> RecommendationReviewRequestResponse:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return RecommendationReviewRequestResponse(
        data=RecommendationReviewRequestResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.post(
    "/{recommendation_id}/human-review-requests",
    response_model=RecommendationReviewRequestResponse,
    status_code=201,
)
async def create_recommendation_review_request(
    recommendation_id: Annotated[str, SAFE_ID],
    payload: RecommendationReviewRequestInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_recommendation_review_request_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> RecommendationReviewRequestResponse:
    service: GovernedRecommendationReviewRequestService = (
        request.app.state.recommendation_review_request_service
    )
    try:
        result = await service.create(
            actor=subject,
            recommendation_id=recommendation_id,
            recommendation_digest=payload.recommendation_digest,
            readiness_assessment_id=payload.readiness_assessment_id,
            readiness_assessment_digest=payload.readiness_assessment_digest,
            review_request_policy_id=payload.review_request_policy_id,
            review_request_policy_digest=payload.review_request_policy_digest,
            purpose=payload.purpose,
            request_is_not_assignment_or_review_acknowledged=(
                payload.acknowledged_request_is_not_assignment_or_review
            ),
            routing_is_policy_owned_acknowledged=(payload.acknowledged_routing_is_policy_owned),
            no_approval_or_operational_authority_acknowledged=(
                payload.acknowledged_no_approval_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except RecommendationReviewRequestError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{recommendation_id}/human-review-requests/{review_request_id}",
    response_model=RecommendationReviewRequestResponse,
)
async def get_recommendation_review_request(
    recommendation_id: Annotated[str, SAFE_ID],
    review_request_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_recommendation_review_request_read)
    ],
) -> RecommendationReviewRequestResponse:
    service: GovernedRecommendationReviewRequestService = (
        request.app.state.recommendation_review_request_service
    )
    try:
        result = await service.get(
            actor=subject,
            review_request_id=review_request_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.recommendation_id != recommendation_id:
            raise RecommendationReviewRequestError("recommendation_review_request_not_found")
    except RecommendationReviewRequestError as error:
        _raise(error)
    return _response(result, request, response)
