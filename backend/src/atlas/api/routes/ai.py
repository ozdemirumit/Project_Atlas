from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from atlas.api.ai_schemas import (
    GroundedAnswerData,
    GroundedAnswerResponse,
    GroundedQueryRequest,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_ai_grounded_query
from atlas.core.classification import DataClassification
from atlas.modules.ai.application.gateway import ModelGatewayError
from atlas.modules.ai.application.service import GroundedAnswerService, GroundedQueryContext
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/grounded-query", response_model=GroundedAnswerResponse)
async def grounded_query(
    payload: GroundedQueryRequest,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_ai_grounded_query)],
) -> GroundedAnswerResponse:
    now = datetime.now(UTC)
    service: GroundedAnswerService = request.app.state.grounded_answer_service
    try:
        answer = await service.answer(
            query=payload.query,
            max_results=payload.max_results,
            context=GroundedQueryContext(
                subject_id=subject.subject_id,
                role_ids=frozenset((*subject.role_ids, *subject.group_ids)),
                organization_id=subject.organization_id,
                environment_id=f"environment.{request.app.state.settings.environment}",
                correlation_id=str(request.state.correlation_id),
                decision_id=decision.decision_id,
                requested_at=now,
                classification_ceiling=DataClassification.INTERNAL,
            ),
        )
    except ModelGatewayError as error:
        raise AtlasError(
            status=503,
            code=error.code,
            title="Grounded answer unavailable",
            detail="The governed model path could not produce a validated answer.",
            retryable=error.code in {"model_timeout", "model_endpoint_unavailable"},
        ) from error
    return GroundedAnswerResponse(
        data=GroundedAnswerData.from_domain(answer),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=now,
        ),
    )
