from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.final_recommendation_disposition_schemas import (
    FinalRecommendationDispositionData,
    FinalRecommendationDispositionInput,
    FinalRecommendationDispositionResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_recommendation_final_disposition_create,
    authorize_recommendation_final_disposition_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.final_disposition import (
    FinalRecommendationDispositionService,
)
from atlas.modules.recommendations.application.final_disposition_ports import (
    FinalRecommendationDispositionError,
    FinalRecommendationDispositionUncertainError,
)
from atlas.modules.recommendations.domain.final_disposition import (
    FinalRecommendationDispositionRecord,
)

router = APIRouter(prefix="/recommendations/review-requests", tags=["recommendations"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: FinalRecommendationDispositionError) -> NoReturn:
    code = str(error)
    if isinstance(error, FinalRecommendationDispositionUncertainError):
        status = 503
    elif code.endswith(("required", "denied", "mfa_required")):
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
        title="Final recommendation disposition unavailable",
        detail=(
            "No recommendation content, finding, workflow, ITSM, change approval, execution, "
            "deployment, or infrastructure authority was returned."
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
    record: FinalRecommendationDispositionRecord,
    request: Request,
    response: Response,
) -> FinalRecommendationDispositionResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return FinalRecommendationDispositionResponse(
        data=FinalRecommendationDispositionData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{review_request_id}/final-dispositions",
    response_model=FinalRecommendationDispositionResponse,
    status_code=201,
)
async def create_final_recommendation_disposition(
    review_request_id: Annotated[str, SAFE_ID],
    payload: FinalRecommendationDispositionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_recommendation_final_disposition_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> FinalRecommendationDispositionResponse:
    service: FinalRecommendationDispositionService = (
        request.app.state.final_recommendation_disposition_service
    )
    try:
        record = await service.create(
            actor=subject,
            review_request_id=review_request_id,
            review_request_digest=payload.review_request_digest,
            recommendation_id=payload.recommendation_id,
            recommendation_digest=payload.recommendation_digest,
            decision_ids=payload.decision_ids,
            decision_digests=payload.decision_digests,
            disposition_code=payload.disposition_code,
            basis_codes=payload.basis_codes,
            disposition_policy_id=payload.disposition_policy_id,
            disposition_policy_digest=payload.disposition_policy_digest,
            purpose=payload.purpose,
            immutable_generation_acknowledged=(payload.acknowledged_immutable_review_generation),
            recommendation_level_only_acknowledged=(
                payload.acknowledged_recommendation_level_decision_only
            ),
            handoff_eligibility_only_acknowledged=(payload.acknowledged_handoff_eligibility_only),
            no_operational_authority_acknowledged=(
                payload.acknowledged_no_workflow_itsm_change_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except FinalRecommendationDispositionError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{review_request_id}/final-dispositions/{disposition_id}",
    response_model=FinalRecommendationDispositionResponse,
)
async def get_final_recommendation_disposition(
    review_request_id: Annotated[str, SAFE_ID],
    disposition_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_recommendation_final_disposition_read),
    ],
) -> FinalRecommendationDispositionResponse:
    service: FinalRecommendationDispositionService = (
        request.app.state.final_recommendation_disposition_service
    )
    try:
        record = await service.get(
            actor=subject,
            disposition_id=disposition_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if record.review_request_id != review_request_id:
            raise FinalRecommendationDispositionError("final_recommendation_disposition_not_found")
    except FinalRecommendationDispositionError as error:
        _raise(error)
    return _response(record, request, response)
