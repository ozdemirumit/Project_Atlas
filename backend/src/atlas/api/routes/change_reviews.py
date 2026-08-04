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
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_upgrade_change_review_create,
    authorize_upgrade_change_review_preview,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.change_review.application.ports import ChangeReviewError
from atlas.modules.change_review.application.service import ChangeReviewService
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
