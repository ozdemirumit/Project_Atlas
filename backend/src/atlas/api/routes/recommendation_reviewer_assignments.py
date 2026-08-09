from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.recommendation_reviewer_assignment_schemas import (
    RecommendationReviewerAssignmentInput,
    RecommendationReviewerAssignmentResponse,
    RecommendationReviewerAssignmentResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_recommendation_reviewer_assignment_create,
    authorize_recommendation_reviewer_assignment_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.reviewer_assignment import (
    GovernedRecommendationReviewerAssignmentService,
)
from atlas.modules.recommendations.application.reviewer_assignment_ports import (
    RecommendationReviewerAssignmentError,
    RecommendationReviewerAssignmentUncertainError,
)
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentResult,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: RecommendationReviewerAssignmentError) -> NoReturn:
    code = str(error)
    status = (
        503
        if isinstance(error, RecommendationReviewerAssignmentUncertainError)
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
        title="Recommendation reviewer assignment unavailable",
        detail=(
            "No content inspection, human finding, decision, approval, workflow, ITSM record, "
            "execution authority, deployment authority, or infrastructure mutation was returned."
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
    result: RecommendationReviewerAssignmentResult,
    request: Request,
    response: Response,
) -> RecommendationReviewerAssignmentResponse:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return RecommendationReviewerAssignmentResponse(
        data=RecommendationReviewerAssignmentResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.post(
    "/{recommendation_id}/reviewer-assignments",
    response_model=RecommendationReviewerAssignmentResponse,
    status_code=201,
)
async def create_recommendation_reviewer_assignment(
    recommendation_id: Annotated[str, SAFE_ID],
    payload: RecommendationReviewerAssignmentInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_recommendation_reviewer_assignment_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> RecommendationReviewerAssignmentResponse:
    service: GovernedRecommendationReviewerAssignmentService = (
        request.app.state.recommendation_reviewer_assignment_service
    )
    try:
        result = await service.create(
            actor=subject,
            recommendation_id=recommendation_id,
            review_request_id=payload.review_request_id,
            review_request_digest=payload.review_request_digest,
            assignment_policy_id=payload.assignment_policy_id,
            assignment_policy_digest=payload.assignment_policy_digest,
            purpose=payload.purpose,
            caller_cannot_select_reviewers_acknowledged=(
                payload.acknowledged_caller_cannot_select_reviewers
            ),
            distinct_reviewers_required_acknowledged=(
                payload.acknowledged_distinct_reviewers_required
            ),
            no_inspection_decision_or_authority_acknowledged=(
                payload.acknowledged_no_inspection_decision_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.recommendation_id != recommendation_id:
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_not_found"
            )
    except RecommendationReviewerAssignmentError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{recommendation_id}/reviewer-assignments/{assignment_set_id}",
    response_model=RecommendationReviewerAssignmentResponse,
)
async def get_recommendation_reviewer_assignment(
    recommendation_id: Annotated[str, SAFE_ID],
    assignment_set_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_recommendation_reviewer_assignment_read)
    ],
) -> RecommendationReviewerAssignmentResponse:
    service: GovernedRecommendationReviewerAssignmentService = (
        request.app.state.recommendation_reviewer_assignment_service
    )
    try:
        result = await service.get(
            actor=subject,
            assignment_set_id=assignment_set_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.recommendation_id != recommendation_id:
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_not_found"
            )
    except RecommendationReviewerAssignmentError as error:
        _raise(error)
    return _response(result, request, response)
