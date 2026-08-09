from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.protected_recommendation_presentation_schemas import (
    ProtectedRecommendationPresentationInput,
    ProtectedRecommendationPresentationResponse,
    ProtectedRecommendationPresentationResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_protected_recommendation_presentation_create,
    authorize_protected_recommendation_presentation_read,
    browser_session_subject,
)
from atlas.modules.ai.application.protected_recommendation_presentation import (
    GovernedProtectedRecommendationPresentationService,
)
from atlas.modules.ai.application.protected_recommendation_presentation_ports import (
    ProtectedRecommendationPresentationError,
    ProtectedRecommendationPresentationUncertainError,
)
from atlas.modules.ai.domain.protected_recommendation_presentation import (
    ProtectedRecommendationPresentationResult,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/ai/recommendation-adjudications", tags=["ai"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ProtectedRecommendationPresentationError) -> NoReturn:
    code = str(error)
    status = (
        503
        if isinstance(error, ProtectedRecommendationPresentationUncertainError)
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
        title="Protected recommendation presentation unavailable",
        detail=(
            "No approval, workflow, execution authority, raw infrastructure identifier, or "
            "executable content was returned."
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
    result: ProtectedRecommendationPresentationResult,
    request: Request,
    response: Response,
) -> ProtectedRecommendationPresentationResponse:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return ProtectedRecommendationPresentationResponse(
        data=ProtectedRecommendationPresentationResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.post(
    "/{adjudication_id}/presentations",
    response_model=ProtectedRecommendationPresentationResponse,
    status_code=201,
)
async def create_protected_recommendation_presentation(
    adjudication_id: Annotated[str, SAFE_ID],
    payload: ProtectedRecommendationPresentationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_protected_recommendation_presentation_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ProtectedRecommendationPresentationResponse:
    service: GovernedProtectedRecommendationPresentationService = (
        request.app.state.protected_recommendation_presentation_service
    )
    try:
        result = await service.create(
            actor=subject,
            adjudication_id=adjudication_id,
            adjudication_digest=payload.adjudication_digest,
            presentation_policy_id=payload.presentation_policy_id,
            presentation_policy_digest=payload.presentation_policy_digest,
            purpose=payload.purpose,
            decision_support_only_acknowledged=payload.acknowledged_decision_support_only,
            tie_or_no_support_acknowledged=payload.acknowledged_tie_or_no_support_is_valid,
            no_operational_authority_acknowledged=payload.acknowledged_no_operational_authority,
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ProtectedRecommendationPresentationError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{adjudication_id}/presentations/{presentation_id}",
    response_model=ProtectedRecommendationPresentationResponse,
)
async def get_protected_recommendation_presentation(
    adjudication_id: Annotated[str, SAFE_ID],
    presentation_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_protected_recommendation_presentation_read)
    ],
) -> ProtectedRecommendationPresentationResponse:
    service: GovernedProtectedRecommendationPresentationService = (
        request.app.state.protected_recommendation_presentation_service
    )
    try:
        result = await service.get(
            actor=subject,
            presentation_id=presentation_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.adjudication_id != adjudication_id:
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_not_found"
            )
    except ProtectedRecommendationPresentationError as error:
        _raise(error)
    return _response(result, request, response)
