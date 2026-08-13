from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.protected_candidate_impact_schemas import (
    ProtectedCandidateImpactInput,
    ProtectedCandidateImpactResponse,
    ProtectedCandidateImpactResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_protected_candidate_impact_create,
    authorize_protected_candidate_impact_read,
    browser_session_subject,
)
from atlas.modules.ai.application.protected_candidate_impact_enrichment import (
    GovernedProtectedCandidateImpactService,
)
from atlas.modules.ai.application.protected_candidate_impact_enrichment_ports import (
    ProtectedCandidateImpactError,
    ProtectedCandidateImpactUncertainError,
)
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactResult,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/ai/recommendation-candidate-sets", tags=["ai"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ProtectedCandidateImpactError) -> NoReturn:
    code = str(error)
    status = (
        503
        if isinstance(error, ProtectedCandidateImpactUncertainError)
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
        title="Protected candidate service-impact enrichment unavailable",
        detail=(
            "No protected impact content, outage claim, recommendation, workflow, or "
            "operational authority was returned."
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
    result: ProtectedCandidateImpactResult, request: Request, response: Response
) -> ProtectedCandidateImpactResponse:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return ProtectedCandidateImpactResponse(
        data=ProtectedCandidateImpactResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{candidate_set_id}/impact-analyses",
    response_model=ProtectedCandidateImpactResponse,
    status_code=201,
)
async def create_protected_candidate_impact(
    candidate_set_id: Annotated[str, SAFE_ID],
    payload: ProtectedCandidateImpactInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_protected_candidate_impact_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ProtectedCandidateImpactResponse:
    service: GovernedProtectedCandidateImpactService = (
        request.app.state.protected_candidate_impact_service
    )
    try:
        result = await service.create(
            actor=subject,
            candidate_set_id=candidate_set_id,
            candidate_set_digest=payload.candidate_set_digest,
            impact_policy_id=payload.impact_policy_id,
            impact_policy_digest=payload.impact_policy_digest,
            purpose=payload.purpose,
            reachability_not_outage_acknowledged=(
                payload.acknowledged_reachability_is_not_outage_evidence
            ),
            impact_provisional_acknowledged=payload.acknowledged_impact_remains_provisional,
            no_recommendation_or_operational_authority_acknowledged=(
                payload.acknowledged_no_recommendation_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ProtectedCandidateImpactError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{candidate_set_id}/impact-analyses/{impact_analysis_id}",
    response_model=ProtectedCandidateImpactResponse,
)
async def get_protected_candidate_impact(
    candidate_set_id: Annotated[str, SAFE_ID],
    impact_analysis_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_protected_candidate_impact_read)],
) -> ProtectedCandidateImpactResponse:
    service: GovernedProtectedCandidateImpactService = (
        request.app.state.protected_candidate_impact_service
    )
    try:
        result = await service.get(
            actor=subject,
            impact_analysis_id=impact_analysis_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.candidate_set_id != candidate_set_id:
            raise ProtectedCandidateImpactError("protected_candidate_impact_not_found")
    except ProtectedCandidateImpactError as error:
        _raise(error)
    return _response(result, request, response)
