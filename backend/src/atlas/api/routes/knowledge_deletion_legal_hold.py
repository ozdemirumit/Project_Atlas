from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.knowledge_deletion_legal_hold_schemas import (
    DeletionCompletePayload,
    DeletionRequestData,
    DeletionRequestPayload,
    DeletionRequestResponse,
    LegalHoldData,
    LegalHoldPlacePayload,
    LegalHoldResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_knowledge_deletion_legal_hold_complete,
    authorize_knowledge_deletion_legal_hold_place,
    authorize_knowledge_deletion_legal_hold_release,
    authorize_knowledge_deletion_legal_hold_request,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.deletion_legal_hold import (
    KnowledgeDeletionError,
    KnowledgeDeletionService,
)
from atlas.modules.knowledge.domain.deletion_legal_hold import DeletionRequest, LegalHold

router = APIRouter(prefix="/knowledge/deletion", tags=["knowledge"])


def _raise(exc: KnowledgeDeletionError) -> NoReturn:
    status_by_code = {
        "knowledge_legal_hold_invalid": 422,
        "knowledge_legal_hold_unavailable": 404,
        "knowledge_legal_hold_already_released": 409,
        "knowledge_deletion_request_invalid": 422,
        "knowledge_deletion_request_unavailable": 404,
        "knowledge_deletion_already_completed": 409,
        "knowledge_deletion_blocked_by_legal_hold": 409,
        "knowledge_deletion_completion_invalid": 422,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 400),
        code=exc.code,
        title="Knowledge deletion and legal hold unavailable",
        detail="The requested knowledge deletion operation could not be completed.",
    ) from exc


def _hold_data(hold: LegalHold) -> LegalHoldData:
    return LegalHoldData(
        hold_id=hold.hold_id,
        item_id=hold.item_id,
        authorized_by=hold.authorized_by,
        reason=hold.reason,
        placed_at=hold.placed_at,
        released_at=hold.released_at,
        release_authorized_by=hold.release_authorized_by,
    )


def _request_data(request_record: DeletionRequest) -> DeletionRequestData:
    return DeletionRequestData(
        request_id=request_record.request_id,
        item_id=request_record.item_id,
        requested_by=request_record.requested_by,
        requested_at=request_record.requested_at,
        retention_policy_reference=request_record.retention_policy_reference,
        state=request_record.state.value,
        completed_at=request_record.completed_at,
        derived_artifacts_removed=request_record.derived_artifacts_removed,
        tombstone_id=request_record.tombstone_id,
    )


@router.post("/legal-holds", response_model=LegalHoldResponse, status_code=201)
async def place_legal_hold(
    payload: LegalHoldPlacePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_knowledge_deletion_legal_hold_place)
    ],
) -> LegalHoldResponse:
    now = datetime.now(UTC)
    service: KnowledgeDeletionService = request.app.state.knowledge_deletion_legal_hold_service
    try:
        hold = await service.place_legal_hold(
            hold_id=payload.hold_id,
            item_id=payload.item_id,
            authorized_by=subject.subject_id,
            reason=payload.reason,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeDeletionError as exc:
        _raise(exc)
    return LegalHoldResponse(
        data=_hold_data(hold),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/legal-holds/{hold_id}/release", response_model=LegalHoldResponse)
async def release_legal_hold(
    hold_id: str,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_knowledge_deletion_legal_hold_release)
    ],
) -> LegalHoldResponse:
    now = datetime.now(UTC)
    service: KnowledgeDeletionService = request.app.state.knowledge_deletion_legal_hold_service
    try:
        hold = await service.release_legal_hold(
            hold_id=hold_id,
            released_by=subject.subject_id,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeDeletionError as exc:
        _raise(exc)
    return LegalHoldResponse(
        data=_hold_data(hold),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/requests", response_model=DeletionRequestResponse, status_code=201)
async def request_deletion(
    payload: DeletionRequestPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_knowledge_deletion_legal_hold_request)
    ],
) -> DeletionRequestResponse:
    now = datetime.now(UTC)
    service: KnowledgeDeletionService = request.app.state.knowledge_deletion_legal_hold_service
    try:
        deletion_request = await service.request_deletion(
            request_id=payload.request_id,
            item_id=payload.item_id,
            requested_by=subject.subject_id,
            retention_policy_reference=payload.retention_policy_reference,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeDeletionError as exc:
        _raise(exc)
    return DeletionRequestResponse(
        data=_request_data(deletion_request),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/requests/{request_id}/complete", response_model=DeletionRequestResponse)
async def complete_deletion(
    request_id: str,
    payload: DeletionCompletePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_knowledge_deletion_legal_hold_complete)
    ],
) -> DeletionRequestResponse:
    now = datetime.now(UTC)
    service: KnowledgeDeletionService = request.app.state.knowledge_deletion_legal_hold_service
    try:
        deletion_request = await service.complete_deletion(
            request_id=request_id,
            tombstone_id=payload.tombstone_id,
            deleted_by=subject.subject_id,
            reason_code=payload.reason_code,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeDeletionError as exc:
        _raise(exc)
    return DeletionRequestResponse(
        data=_request_data(deletion_request),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
