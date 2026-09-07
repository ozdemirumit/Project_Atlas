from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.embedding_model_lifecycle_schemas import (
    EmbeddingModelLifecycleData,
    EmbeddingModelLifecycleResponse,
    EmbeddingModelTransitionPayload,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_knowledge_embedding_model_lifecycle_administer,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.embedding_model_lifecycle import (
    EmbeddingModelLifecycleError,
    EmbeddingModelLifecycleService,
)
from atlas.modules.knowledge.domain.embedding_model_lifecycle import EmbeddingModelLifecycleStage

router = APIRouter(prefix="/knowledge/embedding-models", tags=["knowledge"])
MODEL_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(exc: EmbeddingModelLifecycleError) -> NoReturn:
    status_by_code = {
        "embedding_model_already_registered": 409,
        "embedding_model_unregistered": 404,
        "embedding_model_transition_invalid": 409,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 409),
        code=exc.code,
        title="Embedding model lifecycle unavailable",
        detail="The requested embedding model lifecycle operation could not be completed.",
    ) from exc


@router.post("/{model_id}", response_model=EmbeddingModelLifecycleResponse, status_code=201)
async def register_embedding_model(
    model_id: Annotated[str, MODEL_ID],
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_knowledge_embedding_model_lifecycle_administer),
    ],
) -> EmbeddingModelLifecycleResponse:
    now = datetime.now(UTC)
    service: EmbeddingModelLifecycleService = request.app.state.embedding_model_lifecycle_service
    try:
        stage = await service.register(
            model_id=model_id, correlation_id=str(request.state.correlation_id)
        )
    except EmbeddingModelLifecycleError as exc:
        _raise(exc)
    return EmbeddingModelLifecycleResponse(
        data=EmbeddingModelLifecycleData(model_id=model_id, stage=stage.value),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/{model_id}/transitions", response_model=EmbeddingModelLifecycleResponse)
async def transition_embedding_model(
    model_id: Annotated[str, MODEL_ID],
    payload: EmbeddingModelTransitionPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_knowledge_embedding_model_lifecycle_administer),
    ],
) -> EmbeddingModelLifecycleResponse:
    now = datetime.now(UTC)
    service: EmbeddingModelLifecycleService = request.app.state.embedding_model_lifecycle_service
    try:
        target = EmbeddingModelLifecycleStage(payload.target_stage)
    except ValueError as exc:
        raise AtlasError(
            status=422,
            code="embedding_model_stage_invalid",
            title="Embedding model lifecycle unavailable",
            detail="The target lifecycle stage is not recognized.",
        ) from exc
    try:
        stage = await service.transition(
            model_id=model_id,
            target=target,
            correlation_id=str(request.state.correlation_id),
        )
    except EmbeddingModelLifecycleError as exc:
        _raise(exc)
    return EmbeddingModelLifecycleResponse(
        data=EmbeddingModelLifecycleData(model_id=model_id, stage=stage.value),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
