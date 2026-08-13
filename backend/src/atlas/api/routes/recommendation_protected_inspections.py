from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.recommendation_protected_inspection_schemas import (
    RecommendationProtectedInspectionData,
    RecommendationProtectedInspectionInput,
    RecommendationProtectedInspectionResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_recommendation_protected_inspection_create,
    authorize_recommendation_protected_inspection_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.protected_inspection import (
    RecommendationProtectedInspectionService,
)
from atlas.modules.recommendations.application.protected_inspection_ports import (
    RecommendationProtectedInspectionError,
    RecommendationProtectedInspectionUncertainError,
)
from atlas.modules.recommendations.domain.protected_inspection import (
    RecommendationProtectedInspectionRecord,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: RecommendationProtectedInspectionError) -> NoReturn:
    code = str(error)
    if isinstance(error, RecommendationProtectedInspectionUncertainError):
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
        title="Recommendation protected inspection unavailable",
        detail=(
            "Lease issuance returned no content or bearer material in JSON, recorded no review "
            "decision, and granted no workflow or operational authority. Claimed uncertain "
            "attempts are not retried."
        ),
    ) from error


def _response(
    record: RecommendationProtectedInspectionRecord,
    request: Request,
    response: Response,
) -> RecommendationProtectedInspectionResponse:
    response.headers["Cache-Control"] = "no-store"
    return RecommendationProtectedInspectionResponse(
        data=RecommendationProtectedInspectionData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{recommendation_id}/protected-inspections/leases",
    response_model=RecommendationProtectedInspectionResponse,
    status_code=201,
)
async def create_recommendation_protected_inspection_lease(
    recommendation_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: RecommendationProtectedInspectionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_recommendation_protected_inspection_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> RecommendationProtectedInspectionResponse:
    browser_session_id = getattr(request.state, "authenticated_session_id", None)
    if not isinstance(browser_session_id, str):
        raise AtlasError(
            status=401,
            code="authentication_required",
            title="Authentication required",
            detail="A browser-bound authenticated identity is required.",
        )
    service: RecommendationProtectedInspectionService = (
        request.app.state.recommendation_protected_inspection_service
    )
    try:
        grant = await service.create(
            actor=subject,
            recommendation_id=recommendation_id,
            source_assignment_set_id=payload.source_assignment_set_id,
            source_assignment_set_digest=payload.source_assignment_set_digest,
            track_code=payload.track_code,
            opaque_assignment_id=payload.opaque_assignment_id,
            inspection_policy_id=payload.inspection_policy_id,
            inspection_policy_digest=payload.inspection_policy_digest,
            purpose=payload.purpose,
            lease_only_acknowledged=all(
                (
                    payload.acknowledged_exact_assignee_and_track_required,
                    payload.acknowledged_lease_returns_no_content_or_secret_in_json,
                    payload.acknowledged_no_decision_approval_or_operational_authority,
                )
            ),
            browser_session_id=browser_session_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except RecommendationProtectedInspectionError as error:
        _raise(error)
    if grant.lease_secret is not None:
        track = grant.record.track_code.removeprefix("review-track.")
        response.set_cookie(
            key=f"atlas_recommendation_inspection_{track.replace('-', '_')}",
            value=grant.lease_secret,
            max_age=max(1, int((grant.record.expires_at - grant.record.issued_at).total_seconds())),
            httponly=True,
            secure=request.app.state.settings.environment != "development",
            samesite="strict",
            path=f"/api/v1/recommendations/{recommendation_id}/protected-inspections",
        )
    return _response(grant.record, request, response)


@router.get(
    "/{recommendation_id}/protected-inspections/leases/{lease_id}",
    response_model=RecommendationProtectedInspectionResponse,
)
async def get_recommendation_protected_inspection_lease(
    recommendation_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    lease_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_recommendation_protected_inspection_read),
    ],
) -> RecommendationProtectedInspectionResponse:
    service: RecommendationProtectedInspectionService = (
        request.app.state.recommendation_protected_inspection_service
    )
    try:
        record = await service.get(
            actor=subject,
            lease_id=lease_id,
            correlation_id=str(request.state.correlation_id),
        )
        if record.recommendation_id != recommendation_id:
            raise RecommendationProtectedInspectionError(
                "recommendation_protected_inspection_record_not_found"
            )
    except RecommendationProtectedInspectionError as error:
        _raise(error)
    return _response(record, request, response)
