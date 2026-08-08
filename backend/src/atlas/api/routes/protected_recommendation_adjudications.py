from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.protected_recommendation_adjudication_schemas import (
    ProtectedRecommendationAdjudicationInput,
    ProtectedRecommendationAdjudicationResponse,
    ProtectedRecommendationAdjudicationResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_protected_recommendation_adjudication_create,
    authorize_protected_recommendation_adjudication_read,
    browser_session_subject,
)
from atlas.modules.ai.application.protected_recommendation_adjudication import (
    GovernedProtectedRecommendationAdjudicationService,
)
from atlas.modules.ai.application.protected_recommendation_adjudication_ports import (
    ProtectedRecommendationAdjudicationError,
    ProtectedRecommendationAdjudicationUncertainError,
)
from atlas.modules.ai.domain.protected_recommendation_adjudication import (
    ProtectedRecommendationAdjudicationResult,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/ai/candidate-risk-recovery-completions", tags=["ai"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key",
    min_length=8,
    max_length=128,
    pattern=r"^[A-Za-z0-9._:-]+$",
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ProtectedRecommendationAdjudicationError) -> NoReturn:
    code = str(error)
    status = (
        503
        if isinstance(error, ProtectedRecommendationAdjudicationUncertainError)
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
        title="Protected recommendation adjudication unavailable",
        detail=(
            "No protected candidate content, approval, workflow, review readiness, or operational "
            "authority was returned."
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
    result: ProtectedRecommendationAdjudicationResult,
    request: Request,
    response: Response,
) -> ProtectedRecommendationAdjudicationResponse:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return ProtectedRecommendationAdjudicationResponse(
        data=ProtectedRecommendationAdjudicationResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.post(
    "/{completion_id}/adjudications",
    response_model=ProtectedRecommendationAdjudicationResponse,
    status_code=201,
)
async def create_protected_recommendation_adjudication(
    completion_id: Annotated[str, SAFE_ID],
    payload: ProtectedRecommendationAdjudicationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_protected_recommendation_adjudication_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ProtectedRecommendationAdjudicationResponse:
    service: GovernedProtectedRecommendationAdjudicationService = (
        request.app.state.protected_recommendation_adjudication_service
    )
    try:
        result = await service.create(
            actor=subject,
            completion_id=completion_id,
            completion_digest=payload.completion_digest,
            adjudication_policy_id=payload.adjudication_policy_id,
            adjudication_policy_digest=payload.adjudication_policy_digest,
            purpose=payload.purpose,
            preference_not_approval_acknowledged=(payload.acknowledged_preference_is_not_approval),
            tie_or_no_support_acknowledged=(payload.acknowledged_tie_or_no_support_is_valid),
            no_presentation_or_operational_authority_acknowledged=(
                payload.acknowledged_no_presentation_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ProtectedRecommendationAdjudicationError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{completion_id}/adjudications/{adjudication_id}",
    response_model=ProtectedRecommendationAdjudicationResponse,
)
async def get_protected_recommendation_adjudication(
    completion_id: Annotated[str, SAFE_ID],
    adjudication_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_protected_recommendation_adjudication_read),
    ],
) -> ProtectedRecommendationAdjudicationResponse:
    service: GovernedProtectedRecommendationAdjudicationService = (
        request.app.state.protected_recommendation_adjudication_service
    )
    try:
        result = await service.get(
            actor=subject,
            adjudication_id=adjudication_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.completion_id != completion_id:
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_not_found"
            )
    except ProtectedRecommendationAdjudicationError as error:
        _raise(error)
    return _response(result, request, response)
