from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.recommendation_schemas import (
    RecommendationArtifactData,
    RecommendationCreatePayload,
    RecommendationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_recommendation_create
from atlas.modules.authorization.application.bootstrap import recommendation_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.service import (
    RecommendationAccessContext,
    RecommendationOperationsError,
    RecommendationService,
)
from atlas.modules.recommendations.domain.models import RecommendationRequest

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/storage/{target_id}", response_model=RecommendationResponse)
async def create_storage_recommendation(
    target_id: str,
    payload: RecommendationCreatePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_recommendation_create)],
) -> RecommendationResponse:
    now = datetime.now(UTC)
    scope = recommendation_scope(
        subject.organization_id,
        request.app.state.settings.environment,
    )
    service: RecommendationService = request.app.state.recommendation_service
    try:
        artifact = await service.create(
            RecommendationRequest(
                source_case_id=payload.source_case_id,
                source_case_version=payload.source_case_version,
                target_id=target_id,
                decision_question=payload.decision_question,
                accountable_audience=payload.accountable_audience,
                horizon=payload.horizon,
                constraints=tuple(payload.constraints),
                maximum_capability_class=payload.maximum_capability_class,
                max_options=payload.max_options,
            ),
            context=RecommendationAccessContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                assurance_level=subject.assurance_level.value,
                organization_id=scope.organization_id,
                environment_id=scope.environment_id,
                site_id=scope.site_id,
                resource_id=scope.resource_id,
                correlation_id=str(request.state.correlation_id),
                decision_id=decision.decision_id,
                requested_at=now,
            ),
        )
    except RecommendationOperationsError as exc:
        status = 404 if exc.code == "recommendation_source_unavailable" else 409
        raise AtlasError(
            status=status,
            code=exc.code,
            title="Recommendation unavailable",
            detail=exc.detail,
        ) from exc
    return RecommendationResponse(
        data=RecommendationArtifactData.from_domain(artifact),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
