from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.knowledge_feedback_schemas import (
    FeedbackData,
    FeedbackResolvePayload,
    FeedbackResponse,
    FeedbackSubmitPayload,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_knowledge_feedback_resolve,
    authorize_knowledge_feedback_submit,
    authorize_knowledge_feedback_triage,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.feedback import (
    KnowledgeFeedbackError,
    KnowledgeFeedbackService,
)
from atlas.modules.knowledge.domain.feedback import FeedbackKind, KnowledgeFeedback

router = APIRouter(prefix="/knowledge/feedback", tags=["knowledge"])


def _raise(exc: KnowledgeFeedbackError) -> NoReturn:
    status_by_code = {
        "knowledge_feedback_invalid": 422,
        "knowledge_feedback_kind_invalid": 422,
        "knowledge_feedback_unavailable": 404,
        "knowledge_feedback_already_triaged": 409,
        "knowledge_feedback_not_triaged": 409,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 400),
        code=exc.code,
        title="Knowledge feedback unavailable",
        detail="The requested knowledge feedback operation could not be completed.",
    ) from exc


def _data(feedback: KnowledgeFeedback) -> FeedbackData:
    return FeedbackData(
        feedback_id=feedback.feedback_id,
        item_id=feedback.item_id,
        item_version=feedback.item_version,
        kind=feedback.kind.value,
        submitted_by=feedback.submitted_by,
        submitted_at=feedback.submitted_at,
        description=feedback.description,
        state=feedback.state.value,
        triaged_by=feedback.triaged_by,
        triaged_at=feedback.triaged_at,
        resolution_notes=feedback.resolution_notes,
    )


@router.post("", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    payload: FeedbackSubmitPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_knowledge_feedback_submit)],
) -> FeedbackResponse:
    now = datetime.now(UTC)
    service: KnowledgeFeedbackService = request.app.state.knowledge_feedback_service
    try:
        kind = FeedbackKind(payload.kind)
    except ValueError as exc:
        raise AtlasError(
            status=422,
            code="knowledge_feedback_kind_invalid",
            title="Knowledge feedback unavailable",
            detail="The feedback kind is not recognized.",
        ) from exc
    try:
        feedback = await service.submit(
            item_id=payload.item_id,
            item_version=payload.item_version,
            kind=kind,
            submitted_by=subject.subject_id,
            description=payload.description,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeFeedbackError as exc:
        _raise(exc)
    return FeedbackResponse(
        data=_data(feedback),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/{feedback_id}/triage", response_model=FeedbackResponse)
async def triage_feedback(
    feedback_id: str,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_knowledge_feedback_triage)],
) -> FeedbackResponse:
    now = datetime.now(UTC)
    service: KnowledgeFeedbackService = request.app.state.knowledge_feedback_service
    try:
        feedback = await service.triage(
            feedback_id=feedback_id,
            triaged_by=subject.subject_id,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeFeedbackError as exc:
        _raise(exc)
    return FeedbackResponse(
        data=_data(feedback),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/{feedback_id}/resolve", response_model=FeedbackResponse)
async def resolve_feedback(
    feedback_id: str,
    payload: FeedbackResolvePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_knowledge_feedback_resolve)],
) -> FeedbackResponse:
    now = datetime.now(UTC)
    service: KnowledgeFeedbackService = request.app.state.knowledge_feedback_service
    try:
        feedback = await service.resolve(
            feedback_id=feedback_id,
            resolved_by=subject.subject_id,
            resolution_notes=payload.resolution_notes,
            dismissed=payload.dismissed,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeFeedbackError as exc:
        _raise(exc)
    return FeedbackResponse(
        data=_data(feedback),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
