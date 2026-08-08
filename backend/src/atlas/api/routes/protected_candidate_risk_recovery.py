from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.protected_candidate_risk_recovery_schemas import (
    ProtectedCandidateRiskRecoveryInput,
    ProtectedCandidateRiskRecoveryResponse,
    ProtectedCandidateRiskRecoveryResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_protected_candidate_risk_recovery_create,
    authorize_protected_candidate_risk_recovery_read,
    browser_session_subject,
)
from atlas.modules.ai.application.protected_candidate_risk_recovery_completion import (
    GovernedProtectedCandidateRiskRecoveryService,
)
from atlas.modules.ai.application.protected_candidate_risk_recovery_completion_ports import (
    ProtectedCandidateRiskRecoveryError,
    ProtectedCandidateRiskRecoveryUncertainError,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryResult,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/ai/candidate-impact-analyses", tags=["ai"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key",
    min_length=8,
    max_length=128,
    pattern=r"^[A-Za-z0-9._:-]+$",
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ProtectedCandidateRiskRecoveryError) -> NoReturn:
    code = str(error)
    status = (
        503
        if isinstance(error, ProtectedCandidateRiskRecoveryUncertainError)
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
        title="Protected candidate risk-recovery completion unavailable",
        detail=(
            "No protected candidate assessment, preference, recommendation, workflow, or "
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
    result: ProtectedCandidateRiskRecoveryResult,
    request: Request,
    response: Response,
) -> ProtectedCandidateRiskRecoveryResponse:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return ProtectedCandidateRiskRecoveryResponse(
        data=ProtectedCandidateRiskRecoveryResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.post(
    "/{impact_analysis_id}/risk-recovery-completions",
    response_model=ProtectedCandidateRiskRecoveryResponse,
    status_code=201,
)
async def create_protected_candidate_risk_recovery(
    impact_analysis_id: Annotated[str, SAFE_ID],
    payload: ProtectedCandidateRiskRecoveryInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_protected_candidate_risk_recovery_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ProtectedCandidateRiskRecoveryResponse:
    service: GovernedProtectedCandidateRiskRecoveryService = (
        request.app.state.protected_candidate_risk_recovery_service
    )
    try:
        result = await service.create(
            actor=subject,
            impact_analysis_id=impact_analysis_id,
            impact_digest=payload.impact_digest,
            completion_policy_id=payload.completion_policy_id,
            completion_policy_digest=payload.completion_policy_digest,
            purpose=payload.purpose,
            estimates_not_guarantees_acknowledged=(
                payload.acknowledged_estimates_are_not_guarantees
            ),
            unknowns_cannot_lower_risk_acknowledged=(
                payload.acknowledged_unknowns_cannot_lower_risk
            ),
            no_preference_or_operational_authority_acknowledged=(
                payload.acknowledged_no_preference_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ProtectedCandidateRiskRecoveryError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{impact_analysis_id}/risk-recovery-completions/{completion_id}",
    response_model=ProtectedCandidateRiskRecoveryResponse,
)
async def get_protected_candidate_risk_recovery(
    impact_analysis_id: Annotated[str, SAFE_ID],
    completion_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_protected_candidate_risk_recovery_read),
    ],
) -> ProtectedCandidateRiskRecoveryResponse:
    service: GovernedProtectedCandidateRiskRecoveryService = (
        request.app.state.protected_candidate_risk_recovery_service
    )
    try:
        result = await service.get(
            actor=subject,
            completion_id=completion_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.impact_analysis_id != impact_analysis_id:
            raise ProtectedCandidateRiskRecoveryError("protected_candidate_risk_recovery_not_found")
    except ProtectedCandidateRiskRecoveryError as error:
        _raise(error)
    return _response(result, request, response)
