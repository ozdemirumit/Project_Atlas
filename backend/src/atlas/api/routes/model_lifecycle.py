from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.errors import AtlasError
from atlas.api.model_lifecycle_schemas import (
    ModelLifecycleData,
    ModelLifecycleResponse,
    ModelLifecycleTransitionPayload,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_ai_model_lifecycle_administer
from atlas.modules.ai.application.model_lifecycle import (
    ModelLifecycleError,
    ModelLifecycleService,
)
from atlas.modules.ai.domain.model_lifecycle import ModelLifecycleStage
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/ai/models", tags=["ai"])
MODEL_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(exc: ModelLifecycleError) -> NoReturn:
    status_by_code = {
        "model_lifecycle_already_registered": 409,
        "model_lifecycle_unregistered": 404,
        "model_lifecycle_transition_invalid": 409,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 409),
        code=exc.code,
        title="Model lifecycle unavailable",
        detail="The requested model lifecycle operation could not be completed.",
    ) from exc


@router.post("/{model_id}", response_model=ModelLifecycleResponse, status_code=201)
async def register_model(
    model_id: Annotated[str, MODEL_ID],
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_ai_model_lifecycle_administer)],
) -> ModelLifecycleResponse:
    now = datetime.now(UTC)
    service: ModelLifecycleService = request.app.state.model_lifecycle_service
    try:
        stage = await service.register(
            model_id=model_id, correlation_id=str(request.state.correlation_id)
        )
    except ModelLifecycleError as exc:
        _raise(exc)
    return ModelLifecycleResponse(
        data=ModelLifecycleData(model_id=model_id, stage=stage.value),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/{model_id}/transitions", response_model=ModelLifecycleResponse)
async def transition_model(
    model_id: Annotated[str, MODEL_ID],
    payload: ModelLifecycleTransitionPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_ai_model_lifecycle_administer)],
) -> ModelLifecycleResponse:
    now = datetime.now(UTC)
    service: ModelLifecycleService = request.app.state.model_lifecycle_service
    try:
        target = ModelLifecycleStage(payload.target_stage)
    except ValueError as exc:
        raise AtlasError(
            status=422,
            code="model_lifecycle_stage_invalid",
            title="Model lifecycle unavailable",
            detail="The target lifecycle stage is not recognized.",
        ) from exc
    try:
        stage = await service.transition(
            model_id=model_id,
            target=target,
            correlation_id=str(request.state.correlation_id),
        )
    except ModelLifecycleError as exc:
        _raise(exc)
    return ModelLifecycleResponse(
        data=ModelLifecycleData(model_id=model_id, stage=stage.value),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
