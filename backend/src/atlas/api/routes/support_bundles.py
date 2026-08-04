from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_support_bundle_export,
    authorize_support_bundle_preview,
    browser_session_subject,
)
from atlas.api.support_bundle_schemas import (
    SupportBundleExportData,
    SupportBundleExportInput,
    SupportBundleExportResponse,
    SupportBundlePreviewData,
    SupportBundlePreviewInput,
    SupportBundlePreviewResponse,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.support.application.ports import SupportBundleError
from atlas.modules.support.application.service import SupportBundleService
from atlas.modules.support.domain.support_bundle import SupportTargetState

router = APIRouter(prefix="/platform/support-bundles", tags=["support-bundles"])
IDEMPOTENCY_HEADER = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: SupportBundleError) -> NoReturn:
    status = 404 if error.code.endswith("unavailable") else 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="Support bundle unavailable",
        detail="The bounded local support bundle request cannot be satisfied safely.",
    ) from error


@router.post("/preview", response_model=SupportBundlePreviewResponse)
async def preview_support_bundle(
    payload: SupportBundlePreviewInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_support_bundle_preview)],
) -> SupportBundlePreviewResponse:
    service: SupportBundleService = request.app.state.support_bundle_service
    try:
        preview = await service.preview(
            actor=subject,
            **payload.model_dump(exclude={"schema_version"}),
        )
    except SupportBundleError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return SupportBundlePreviewResponse(
        data=SupportBundlePreviewData.from_domain(preview),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("/{source_run_id}/exports", response_model=SupportBundleExportResponse)
async def export_support_bundle(
    source_run_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: SupportBundleExportInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_support_bundle_export)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> SupportBundleExportResponse:
    service: SupportBundleService = request.app.state.support_bundle_service
    try:
        result = await service.export(
            actor=subject,
            source_run_id=source_run_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            expected_target_state=SupportTargetState(payload.expected_target_state),
            **payload.model_dump(exclude={"schema_version", "expected_target_state"}),
        )
    except SupportBundleError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return SupportBundleExportResponse(
        data=SupportBundleExportData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
