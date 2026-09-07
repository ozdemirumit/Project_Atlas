from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.errors import AtlasError
from atlas.api.recommendation_outcome_schemas import (
    RecommendationOutcomeData,
    RecommendationOutcomeInput,
    RecommendationOutcomeResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_recommendation_outcome_read,
    authorize_recommendation_outcome_record,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.outcome_learning import (
    RecommendationOutcomeError,
    RecommendationOutcomeService,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
RECOMMENDATION_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


def _raise(exc: RecommendationOutcomeError) -> NoReturn:
    status_by_code = {
        "recommendation_outcome_invalid": 422,
        "recommendation_outcome_already_recorded": 409,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 400),
        code=exc.code,
        title="Recommendation outcome unavailable",
        detail="The requested recommendation outcome operation could not be completed.",
    ) from exc


@router.post(
    "/{recommendation_id}/outcomes", response_model=RecommendationOutcomeResponse, status_code=201
)
async def record_recommendation_outcome(
    recommendation_id: Annotated[str, RECOMMENDATION_ID],
    payload: RecommendationOutcomeInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_recommendation_outcome_record)],
) -> RecommendationOutcomeResponse:
    service: RecommendationOutcomeService = request.app.state.recommendation_outcome_service
    try:
        record = await service.record_outcome(
            recommendation_id=recommendation_id,
            recommendation_version=payload.recommendation_version,
            plan_option_id=payload.plan_option_id,
            recorded_by=payload.recorded_by,
            deviations_from_plan=tuple(payload.deviations_from_plan),
            actual_started_at=payload.actual_started_at,
            actual_duration_minutes=payload.actual_duration_minutes,
            actual_interruption_minutes=payload.actual_interruption_minutes,
            affected_scope=tuple(payload.affected_scope),
            result=payload.result,
            actual_root_cause=payload.actual_root_cause,
            root_cause_validated=payload.root_cause_validated,
            new_incidents=tuple(payload.new_incidents),
            side_effects=tuple(payload.side_effects),
            reviewer_lessons=payload.reviewer_lessons,
            follow_up=tuple(payload.follow_up),
            correlation_id=str(request.state.correlation_id),
        )
    except RecommendationOutcomeError as exc:
        _raise(exc)
    return RecommendationOutcomeResponse(
        data=RecommendationOutcomeData.from_domain(record), meta=_meta(request)
    )


@router.get("/{recommendation_id}/outcomes", response_model=RecommendationOutcomeResponse)
async def get_recommendation_outcome(
    recommendation_id: Annotated[str, RECOMMENDATION_ID],
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_recommendation_outcome_read)],
) -> RecommendationOutcomeResponse:
    service: RecommendationOutcomeService = request.app.state.recommendation_outcome_service
    record = await service.get_outcome(recommendation_id)
    if record is None:
        raise AtlasError(
            status=404,
            code="recommendation_outcome_not_found",
            title="Recommendation outcome unavailable",
            detail="No recommendation outcome has been recorded for this recommendation.",
        )
    return RecommendationOutcomeResponse(
        data=RecommendationOutcomeData.from_domain(record), meta=_meta(request)
    )
