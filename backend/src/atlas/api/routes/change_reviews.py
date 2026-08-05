from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.change_review_schemas import (
    ChangeReviewCreateInput,
    ChangeReviewPacketData,
    ChangeReviewPacketResponse,
    ChangeReviewPreviewData,
    ChangeReviewPreviewInput,
    ChangeReviewPreviewResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.human_review_schemas import (
    HumanReviewCreateInput,
    HumanReviewData,
    HumanReviewDecisionInput,
    HumanReviewResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_upgrade_change_review_create,
    authorize_upgrade_change_review_preview,
    authorize_upgrade_human_review_create,
    authorize_upgrade_human_review_decide,
    authorize_upgrade_human_review_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.change_review.application.human_review_service import HumanReviewService
from atlas.modules.change_review.application.ports import ChangeReviewError
from atlas.modules.change_review.application.service import ChangeReviewService
from atlas.modules.change_review.domain.human_review import HumanReviewOutcome
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/platform/upgrade-change-reviews", tags=["upgrade-change-review"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key",
    min_length=8,
    max_length=128,
    pattern=r"^[A-Za-z0-9._:-]+$",
)


def _raise(error: ChangeReviewError) -> NoReturn:
    status = 404 if error.code.endswith("unavailable") else 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="Upgrade change review unavailable",
        detail="The evidence-bound upgrade change review cannot proceed safely.",
    ) from error


@router.post("/preview", response_model=ChangeReviewPreviewResponse)
async def preview_change_review(
    payload: ChangeReviewPreviewInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_upgrade_change_review_preview)],
) -> ChangeReviewPreviewResponse:
    service: ChangeReviewService = request.app.state.change_review_service
    try:
        result = await service.preview(
            actor=subject, **payload.model_dump(exclude={"schema_version"})
        )
    except ChangeReviewError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ChangeReviewPreviewResponse(
        data=ChangeReviewPreviewData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.post("/{source_run_id}/packets", response_model=ChangeReviewPacketResponse)
async def create_change_review_packet(
    source_run_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ChangeReviewCreateInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_upgrade_change_review_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ChangeReviewPacketResponse:
    if payload.source_run_id != source_run_id:
        _raise(ChangeReviewError("change_review_source_mismatch"))
    service: ChangeReviewService = request.app.state.change_review_service
    try:
        result = await service.create_packet(
            actor=subject,
            source_run_id=source_run_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version", "source_run_id"}),
        )
    except ChangeReviewError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ChangeReviewPacketResponse(
        data=ChangeReviewPacketData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.post("/{packet_id}/human-reviews", response_model=HumanReviewResponse)
async def create_human_review(
    packet_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: HumanReviewCreateInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_upgrade_human_review_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> HumanReviewResponse:
    if payload.packet_id != packet_id:
        _raise(ChangeReviewError("human_review_source_mismatch"))
    service: HumanReviewService = request.app.state.human_review_service
    try:
        result = await service.create(
            actor=subject,
            packet_id=packet_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version", "packet_id"}),
        )
    except ChangeReviewError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return HumanReviewResponse(
        data=HumanReviewData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/human-reviews/{review_id}", response_model=HumanReviewResponse)
async def get_human_review(
    review_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_upgrade_human_review_read)],
) -> HumanReviewResponse:
    service: HumanReviewService = request.app.state.human_review_service
    try:
        result = await service.get(
            actor=subject,
            review_id=review_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ChangeReviewError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return HumanReviewResponse(
        data=HumanReviewData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("/human-reviews/{review_id}/decisions", response_model=HumanReviewResponse)
async def decide_human_review(
    review_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: HumanReviewDecisionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_upgrade_human_review_decide)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> HumanReviewResponse:
    service: HumanReviewService = request.app.state.human_review_service
    try:
        result = await service.decide(
            actor=subject,
            review_id=review_id,
            stage_id=payload.stage_id,
            outcome=HumanReviewOutcome(payload.outcome),
            rationale=payload.rationale,
            expected_version=payload.expected_version,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ChangeReviewError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return HumanReviewResponse(
        data=HumanReviewData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
