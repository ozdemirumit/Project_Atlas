from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.knowledge_review_expiry_schemas import (
    OwnerAbsenceResolutionData,
    OwnerAbsenceResolutionResponse,
    OwnerAbsenceResolvePayload,
    ReviewDueData,
    ReviewDueResponse,
    ReviewRenewalData,
    ReviewRenewalResponse,
    ReviewRenewPayload,
    ReviewSchedulePayload,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_knowledge_review_expiry_owner_absence_resolve,
    authorize_knowledge_review_expiry_renew,
    authorize_knowledge_review_expiry_schedule,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.review_expiry import (
    KnowledgeReviewError,
    KnowledgeReviewService,
)
from atlas.modules.knowledge.domain.review_expiry import (
    OwnerAbsenceResolution,
    OwnerAbsenceResolutionKind,
    ReviewDueRecord,
    ReviewRenewal,
)

router = APIRouter(prefix="/knowledge/review-expiry", tags=["knowledge"])


def _raise(exc: KnowledgeReviewError) -> NoReturn:
    status_by_code = {
        "knowledge_review_invalid": 422,
        "knowledge_review_unavailable": 404,
        "knowledge_review_renewal_invalid": 422,
        "knowledge_review_owner_absence_invalid": 422,
        "knowledge_review_owner_absence_resolution_invalid": 422,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 400),
        code=exc.code,
        title="Knowledge review and expiry unavailable",
        detail="The requested knowledge review operation could not be completed.",
    ) from exc


def _due_data(record: ReviewDueRecord) -> ReviewDueData:
    return ReviewDueData(
        item_id=record.item_id,
        item_version=record.item_version,
        owner=record.owner,
        review_interval_days=record.review_interval_days,
        last_reviewed_at=record.last_reviewed_at,
        next_review_due_at=record.next_review_due_at,
    )


def _renewal_data(renewal: ReviewRenewal) -> ReviewRenewalData:
    return ReviewRenewalData(
        item_id=renewal.item_id,
        item_version=renewal.item_version,
        renewed_by=renewal.renewed_by,
        renewed_at=renewal.renewed_at,
        evidence_reference=renewal.evidence_reference,
        next_review_due_at=renewal.next_review_due_at,
    )


def _owner_absence_data(record: OwnerAbsenceResolution) -> OwnerAbsenceResolutionData:
    return OwnerAbsenceResolutionData(
        item_id=record.item_id,
        prior_owner=record.prior_owner,
        resolution=record.resolution.value,
        new_owner=record.new_owner,
        resolved_by=record.resolved_by,
        resolved_at=record.resolved_at,
        rationale=record.rationale,
    )


@router.post("/{item_id}", response_model=ReviewDueResponse, status_code=201)
async def schedule_review(
    item_id: str,
    payload: ReviewSchedulePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_knowledge_review_expiry_schedule)
    ],
) -> ReviewDueResponse:
    now = datetime.now(UTC)
    service: KnowledgeReviewService = request.app.state.knowledge_review_expiry_service
    try:
        record = await service.schedule_review(
            item_id=item_id,
            item_version=payload.item_version,
            owner=payload.owner,
            review_interval_days=payload.review_interval_days,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeReviewError as exc:
        _raise(exc)
    return ReviewDueResponse(
        data=_due_data(record),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/{item_id}/renew", response_model=ReviewRenewalResponse)
async def renew_review(
    item_id: str,
    payload: ReviewRenewPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_knowledge_review_expiry_renew)],
) -> ReviewRenewalResponse:
    now = datetime.now(UTC)
    service: KnowledgeReviewService = request.app.state.knowledge_review_expiry_service
    try:
        renewal = await service.renew(
            item_id=item_id,
            renewed_by=subject.subject_id,
            evidence_reference=payload.evidence_reference,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeReviewError as exc:
        _raise(exc)
    return ReviewRenewalResponse(
        data=_renewal_data(renewal),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post(
    "/{item_id}/owner-absence-resolution",
    response_model=OwnerAbsenceResolutionResponse,
)
async def resolve_owner_absence(
    item_id: str,
    payload: OwnerAbsenceResolvePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_knowledge_review_expiry_owner_absence_resolve)
    ],
) -> OwnerAbsenceResolutionResponse:
    now = datetime.now(UTC)
    service: KnowledgeReviewService = request.app.state.knowledge_review_expiry_service
    try:
        resolution = OwnerAbsenceResolutionKind(payload.resolution)
    except ValueError as exc:
        raise AtlasError(
            status=422,
            code="knowledge_review_owner_absence_resolution_invalid",
            title="Knowledge review and expiry unavailable",
            detail="The owner absence resolution kind is not recognized.",
        ) from exc
    try:
        record = await service.resolve_owner_absence(
            item_id=item_id,
            resolution=resolution,
            new_owner=payload.new_owner,
            resolved_by=subject.subject_id,
            rationale=payload.rationale,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeReviewError as exc:
        _raise(exc)
    return OwnerAbsenceResolutionResponse(
        data=_owner_absence_data(record),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
