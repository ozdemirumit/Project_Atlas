from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.recovery_schemas import (
    BackupCreateInput,
    BackupData,
    BackupPreviewData,
    BackupPreviewInput,
    BackupPreviewResponse,
    BackupResponse,
    RestoreValidationData,
    RestoreValidationInput,
    RestoreValidationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_backup_create,
    authorize_backup_preview,
    authorize_restore_validation,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recovery.application.ports import RecoveryError
from atlas.modules.recovery.application.service import RecoveryService
from atlas.modules.recovery.domain.backup import BackupTargetState

router = APIRouter(prefix="/platform/backups", tags=["backup-recovery"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: RecoveryError) -> NoReturn:
    status = 404 if error.code.endswith("unavailable") else 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="Backup or validation unavailable",
        detail="The bounded backup or isolated validation request cannot be satisfied safely.",
    ) from error


@router.post("/preview", response_model=BackupPreviewResponse)
async def preview_backup(
    payload: BackupPreviewInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_backup_preview)],
) -> BackupPreviewResponse:
    service: RecoveryService = request.app.state.recovery_service
    try:
        result = await service.preview(
            actor=subject, **payload.model_dump(exclude={"schema_version"})
        )
    except RecoveryError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return BackupPreviewResponse(
        data=BackupPreviewData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("/{source_run_id}", response_model=BackupResponse)
async def create_backup(
    source_run_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: BackupCreateInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_backup_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> BackupResponse:
    service: RecoveryService = request.app.state.recovery_service
    try:
        result = await service.create_backup(
            actor=subject,
            source_run_id=source_run_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            expected_target_state=BackupTargetState(payload.expected_target_state),
            **payload.model_dump(exclude={"schema_version", "expected_target_state"}),
        )
    except RecoveryError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return BackupResponse(
        data=BackupData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("/{backup_id}/restore-validations", response_model=RestoreValidationResponse)
async def validate_restore(
    backup_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: RestoreValidationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_restore_validation)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> RestoreValidationResponse:
    service: RecoveryService = request.app.state.recovery_service
    try:
        result = await service.validate_restore(
            actor=subject,
            backup_id=backup_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except RecoveryError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return RestoreValidationResponse(
        data=RestoreValidationData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
