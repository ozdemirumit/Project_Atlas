from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.recommendation_promotion_schemas import (
    RecommendationPromotionInput,
    RecommendationPromotionResponse,
    RecommendationPromotionResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_recommendation_promotion_create,
    authorize_recommendation_promotion_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.promotion import (
    GovernedRecommendationPromotionService,
)
from atlas.modules.recommendations.application.promotion_ports import (
    RecommendationPromotionError,
    RecommendationPromotionUncertainError,
)
from atlas.modules.recommendations.domain.promotion import RecommendationPromotionResult

router = APIRouter(prefix="/recommendation-presentations", tags=["recommendations"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: RecommendationPromotionError) -> NoReturn:
    code = str(error)
    status = (
        503
        if isinstance(error, RecommendationPromotionUncertainError)
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
        title="Recommendation promotion unavailable",
        detail=(
            "No review readiness, approval, workflow, execution authority, raw protected "
            "content, or infrastructure mutation was returned."
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
    result: RecommendationPromotionResult,
    request: Request,
    response: Response,
) -> RecommendationPromotionResponse:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return RecommendationPromotionResponse(
        data=RecommendationPromotionResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.post(
    "/{presentation_id}/promotions",
    response_model=RecommendationPromotionResponse,
    status_code=201,
)
async def create_recommendation_promotion(
    presentation_id: Annotated[str, SAFE_ID],
    payload: RecommendationPromotionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_recommendation_promotion_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> RecommendationPromotionResponse:
    service: GovernedRecommendationPromotionService = (
        request.app.state.recommendation_promotion_service
    )
    try:
        result = await service.create(
            actor=subject,
            presentation_id=presentation_id,
            presentation_digest=payload.presentation_digest,
            promotion_policy_id=payload.promotion_policy_id,
            promotion_policy_digest=payload.promotion_policy_digest,
            purpose=payload.purpose,
            draft_only_acknowledged=payload.acknowledged_draft_only,
            no_review_or_approval_acknowledged=payload.acknowledged_no_review_or_approval,
            no_operational_authority_acknowledged=payload.acknowledged_no_operational_authority,
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except RecommendationPromotionError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{presentation_id}/promotions/{recommendation_id}",
    response_model=RecommendationPromotionResponse,
)
async def get_recommendation_promotion(
    presentation_id: Annotated[str, SAFE_ID],
    recommendation_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_recommendation_promotion_read)],
) -> RecommendationPromotionResponse:
    service: GovernedRecommendationPromotionService = (
        request.app.state.recommendation_promotion_service
    )
    try:
        result = await service.get(
            actor=subject,
            recommendation_id=recommendation_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.artifact.presentation_id != presentation_id:
            raise RecommendationPromotionError("recommendation_promotion_not_found")
    except RecommendationPromotionError as error:
        _raise(error)
    return _response(result, request, response)
