from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.recommendation_readiness_schemas import (
    RecommendationReadinessInput,
    RecommendationReadinessResponse,
    RecommendationReadinessResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_recommendation_readiness_create,
    authorize_recommendation_readiness_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.readiness import (
    GovernedRecommendationReadinessService,
)
from atlas.modules.recommendations.application.readiness_ports import (
    RecommendationReadinessError,
    RecommendationReadinessUncertainError,
)
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessResult

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: RecommendationReadinessError) -> NoReturn:
    code = str(error)
    status = (
        503
        if isinstance(error, RecommendationReadinessUncertainError)
        else 403
        if code.endswith(("required", "denied"))
        else 404
        if code.endswith(("not_found", "unavailable"))
        else 422
        if code.endswith(("invalid", "integrity_failed"))
        else 409
    )
    raise AtlasError(
        status=status,
        code=code,
        title="Recommendation review-readiness assessment unavailable",
        detail=(
            "No human review, approval, workflow, ITSM record, execution authority, "
            "deployment authority, or infrastructure mutation was returned."
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
    result: RecommendationReadinessResult,
    request: Request,
    response: Response,
) -> RecommendationReadinessResponse:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return RecommendationReadinessResponse(
        data=RecommendationReadinessResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.post(
    "/{recommendation_id}/review-readiness-assessments",
    response_model=RecommendationReadinessResponse,
    status_code=201,
)
async def create_recommendation_readiness(
    recommendation_id: Annotated[str, SAFE_ID],
    payload: RecommendationReadinessInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_recommendation_readiness_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> RecommendationReadinessResponse:
    service: GovernedRecommendationReadinessService = (
        request.app.state.recommendation_readiness_service
    )
    try:
        result = await service.create(
            actor=subject,
            recommendation_id=recommendation_id,
            recommendation_digest=payload.recommendation_digest,
            readiness_policy_id=payload.readiness_policy_id,
            readiness_policy_digest=payload.readiness_policy_digest,
            purpose=payload.purpose,
            readiness_is_not_review_acknowledged=(payload.acknowledged_readiness_is_not_review),
            blocked_requires_new_version_acknowledged=(
                payload.acknowledged_blocked_requires_new_version
            ),
            no_operational_authority_acknowledged=(payload.acknowledged_no_operational_authority),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except RecommendationReadinessError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{recommendation_id}/review-readiness-assessments/{assessment_id}",
    response_model=RecommendationReadinessResponse,
)
async def get_recommendation_readiness(
    recommendation_id: Annotated[str, SAFE_ID],
    assessment_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_recommendation_readiness_read)],
) -> RecommendationReadinessResponse:
    service: GovernedRecommendationReadinessService = (
        request.app.state.recommendation_readiness_service
    )
    try:
        result = await service.get(
            actor=subject,
            assessment_id=assessment_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.assessment.recommendation_id != recommendation_id:
            raise RecommendationReadinessError("recommendation_readiness_not_found")
    except RecommendationReadinessError as error:
        _raise(error)
    return _response(result, request, response)
