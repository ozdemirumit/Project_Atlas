from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.recommendation_protected_content_schemas import (
    RecommendationProtectedContentData,
    RecommendationProtectedContentInput,
    RecommendationProtectedContentResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_recommendation_protected_content_create,
    authorize_recommendation_protected_content_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.protected_content import (
    RecommendationProtectedContentService,
)
from atlas.modules.recommendations.application.protected_content_ports import (
    RecommendationProtectedContentError,
    RecommendationProtectedContentUncertainError,
)
from atlas.modules.recommendations.domain.protected_content import (
    RecommendationProtectedContentGrant,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: RecommendationProtectedContentError) -> NoReturn:
    code = str(error)
    if isinstance(error, RecommendationProtectedContentUncertainError):
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
        title="Recommendation protected content unavailable",
        detail=(
            "No partial content, finding, decision, approval, workflow, ITSM, or operational "
            "authority was returned. Claimed uncertain first presentations are not retried."
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
    grant: RecommendationProtectedContentGrant, request: Request, response: Response
) -> RecommendationProtectedContentResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return RecommendationProtectedContentResponse(
        data=RecommendationProtectedContentData.from_grant(grant),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{recommendation_id}/protected-inspections/leases/{lease_id}/presentations",
    response_model=RecommendationProtectedContentResponse,
    status_code=201,
)
async def create_recommendation_protected_content_presentation(
    recommendation_id: Annotated[str, SAFE_ID],
    lease_id: Annotated[str, SAFE_ID],
    payload: RecommendationProtectedContentInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_recommendation_protected_content_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> RecommendationProtectedContentResponse:
    service: RecommendationProtectedContentService = (
        request.app.state.recommendation_protected_content_service
    )
    try:
        grant = await service.create(
            actor=subject,
            recommendation_id=recommendation_id,
            source_lease_id=lease_id,
            source_lease_digest=payload.source_lease_digest,
            presentation_policy_id=payload.presentation_policy_id,
            presentation_policy_digest=payload.presentation_policy_digest,
            purpose=payload.purpose,
            sensitive_read_only_acknowledged=all(
                (
                    payload.acknowledged_sensitive_read_only_content,
                    payload.acknowledged_no_finding_decision_approval_or_operational_authority,
                )
            ),
            browser_session_id=_browser_session_id(request),
            lease_secrets=_lease_secrets(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except RecommendationProtectedContentError as error:
        _raise(error)
    return _response(grant, request, response)


@router.get(
    "/{recommendation_id}/protected-inspections/leases/{lease_id}/presentations/{presentation_id}",
    response_model=RecommendationProtectedContentResponse,
)
async def get_recommendation_protected_content_presentation(
    recommendation_id: Annotated[str, SAFE_ID],
    lease_id: Annotated[str, SAFE_ID],
    presentation_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_recommendation_protected_content_read)
    ],
) -> RecommendationProtectedContentResponse:
    service: RecommendationProtectedContentService = (
        request.app.state.recommendation_protected_content_service
    )
    try:
        grant = await service.get(
            actor=subject,
            recommendation_id=recommendation_id,
            source_lease_id=lease_id,
            presentation_id=presentation_id,
            browser_session_id=_browser_session_id(request),
            lease_secrets=_lease_secrets(request),
            correlation_id=str(request.state.correlation_id),
        )
    except RecommendationProtectedContentError as error:
        _raise(error)
    return _response(grant, request, response)
