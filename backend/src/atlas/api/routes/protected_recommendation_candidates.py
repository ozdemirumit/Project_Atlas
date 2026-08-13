from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.protected_recommendation_candidate_schemas import (
    ProtectedRecommendationCandidateInput,
    ProtectedRecommendationCandidateResponse,
    ProtectedRecommendationCandidateResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_protected_recommendation_candidate_create,
    authorize_protected_recommendation_candidate_read,
    browser_session_subject,
)
from atlas.modules.ai.application.protected_recommendation_candidate_generation import (
    GovernedProtectedRecommendationCandidateService,
)
from atlas.modules.ai.application.protected_recommendation_candidate_generation_ports import (
    ProtectedRecommendationCandidateError,
    ProtectedRecommendationCandidateUncertainError,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateResult,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/ai/answer-presentations", tags=["ai"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ProtectedRecommendationCandidateError) -> NoReturn:
    code = str(error)
    status = (
        503
        if isinstance(error, ProtectedRecommendationCandidateUncertainError)
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
        title="Protected recommendation-candidate generation unavailable",
        detail=(
            "No candidate content, recommendation, preference, impact, workflow, or operational "
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
    result: ProtectedRecommendationCandidateResult,
    request: Request,
    response: Response,
) -> ProtectedRecommendationCandidateResponse:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return ProtectedRecommendationCandidateResponse(
        data=ProtectedRecommendationCandidateResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{presentation_id}/recommendation-candidate-sets",
    response_model=ProtectedRecommendationCandidateResponse,
    status_code=201,
)
async def create_protected_recommendation_candidate_set(
    presentation_id: Annotated[str, SAFE_ID],
    payload: ProtectedRecommendationCandidateInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_protected_recommendation_candidate_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ProtectedRecommendationCandidateResponse:
    service: GovernedProtectedRecommendationCandidateService = (
        request.app.state.protected_recommendation_candidate_service
    )
    try:
        result = await service.create(
            actor=subject,
            presentation_id=presentation_id,
            presentation_digest=payload.presentation_digest,
            generation_policy_id=payload.generation_policy_id,
            generation_policy_digest=payload.generation_policy_digest,
            purpose=payload.purpose,
            incomplete_candidates_acknowledged=(payload.acknowledged_candidates_are_incomplete),
            impact_and_recovery_unverified_acknowledged=(
                payload.acknowledged_impact_and_recovery_are_unverified
            ),
            no_recommendation_or_operational_authority_acknowledged=(
                payload.acknowledged_no_recommendation_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ProtectedRecommendationCandidateError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{presentation_id}/recommendation-candidate-sets/{candidate_set_id}",
    response_model=ProtectedRecommendationCandidateResponse,
)
async def get_protected_recommendation_candidate_set(
    presentation_id: Annotated[str, SAFE_ID],
    candidate_set_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_protected_recommendation_candidate_read)
    ],
) -> ProtectedRecommendationCandidateResponse:
    service: GovernedProtectedRecommendationCandidateService = (
        request.app.state.protected_recommendation_candidate_service
    )
    try:
        result = await service.get(
            actor=subject,
            candidate_set_id=candidate_set_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.presentation_id != presentation_id:
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_not_found"
            )
    except ProtectedRecommendationCandidateError as error:
        _raise(error)
    return _response(result, request, response)
