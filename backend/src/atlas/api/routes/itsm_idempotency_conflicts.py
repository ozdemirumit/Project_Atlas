from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.errors import AtlasError
from atlas.api.itsm_idempotency_conflict_schemas import (
    ItsmConflictData,
    ItsmConflictResponse,
    ItsmCreationIntentData,
    ItsmCreationIntentResponse,
    RecordItsmConflictPayload,
    RecordItsmCreationIntentPayload,
    ResolveItsmConflictPayload,
    ResolveItsmCreationIntentPayload,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_itsm_idempotency_conflict_manage,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.itsm.application.idempotency_conflict import (
    ItsmIdempotencyConflictError,
    ItsmIdempotencyConflictService,
)
from atlas.modules.itsm.domain.idempotency_conflict import (
    ItsmConflictKind,
    ItsmConflictRecord,
    ItsmCreationIntent,
    ItsmCreationIntentState,
    ItsmFieldOwnership,
)

router = APIRouter(prefix="/itsm/idempotency-conflicts", tags=["itsm"])
INTENT_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
CONFLICT_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ItsmIdempotencyConflictError) -> NoReturn:
    if error.code.endswith("not_found"):
        status = 404
    elif error.code.endswith(("invalid", "not_terminal")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="ITSM idempotency/conflict operation unavailable",
        detail="The requested creation-intent or conflict operation could not be completed.",
    ) from error


def _intent_data(intent: ItsmCreationIntent) -> ItsmCreationIntentData:
    return ItsmCreationIntentData(
        intent_id=intent.intent_id,
        idempotency_key=intent.idempotency_key,
        profile_id=intent.profile_id,
        operation=intent.operation,
        deduplication_signature=intent.deduplication_signature,
        state=intent.state.value,
        created_at=intent.created_at.isoformat(),
        resolved_at=intent.resolved_at.isoformat() if intent.resolved_at else None,
        external_record_id=intent.external_record_id,
    )


def _conflict_data(conflict: ItsmConflictRecord) -> ItsmConflictData:
    return ItsmConflictData(
        conflict_id=conflict.conflict_id,
        profile_id=conflict.profile_id,
        external_record_id=conflict.external_record_id,
        kind=conflict.kind.value,
        last_known_source_version=conflict.last_known_source_version,
        observed_source_version=conflict.observed_source_version,
        field_ownership=conflict.field_ownership.value,
        detected_at=conflict.detected_at.isoformat(),
        resolution_summary=conflict.resolution_summary,
        resolved_by=conflict.resolved_by,
        resolved_at=conflict.resolved_at.isoformat() if conflict.resolved_at else None,
    )


@router.post("/intents/{intent_id}", response_model=ItsmCreationIntentResponse, status_code=201)
async def record_creation_intent(
    intent_id: Annotated[str, INTENT_ID],
    payload: RecordItsmCreationIntentPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_itsm_idempotency_conflict_manage)
    ],
) -> ItsmCreationIntentResponse:
    now = datetime.now(UTC)
    service: ItsmIdempotencyConflictService = request.app.state.itsm_idempotency_conflict_service
    try:
        intent = await service.record_creation_intent(
            intent_id=intent_id,
            idempotency_key=payload.idempotency_key,
            profile_id=payload.profile_id,
            operation=payload.operation,
            deduplication_signature=payload.deduplication_signature,
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmIdempotencyConflictError as error:
        _raise(error)
    return ItsmCreationIntentResponse(
        data=_intent_data(intent),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/intents/{intent_id}/dispatch", response_model=ItsmCreationIntentResponse)
async def mark_creation_intent_dispatched(
    intent_id: Annotated[str, INTENT_ID],
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_itsm_idempotency_conflict_manage)
    ],
) -> ItsmCreationIntentResponse:
    now = datetime.now(UTC)
    service: ItsmIdempotencyConflictService = request.app.state.itsm_idempotency_conflict_service
    try:
        intent = await service.mark_dispatched(
            intent_id=intent_id,
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmIdempotencyConflictError as error:
        _raise(error)
    return ItsmCreationIntentResponse(
        data=_intent_data(intent),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/intents/{intent_id}/resolution", response_model=ItsmCreationIntentResponse)
async def resolve_creation_intent(
    intent_id: Annotated[str, INTENT_ID],
    payload: ResolveItsmCreationIntentPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_itsm_idempotency_conflict_manage)
    ],
) -> ItsmCreationIntentResponse:
    now = datetime.now(UTC)
    try:
        resolution = ItsmCreationIntentState(payload.resolution)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="itsm_creation_intent_resolution_unrecognized",
            title="ITSM idempotency/conflict operation unavailable",
            detail="The resolution state is not recognized.",
        ) from error
    service: ItsmIdempotencyConflictService = request.app.state.itsm_idempotency_conflict_service
    try:
        intent = await service.resolve_creation_intent(
            intent_id=intent_id,
            resolution=resolution,
            external_record_id=payload.external_record_id,
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmIdempotencyConflictError as error:
        _raise(error)
    return ItsmCreationIntentResponse(
        data=_intent_data(intent),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/conflicts/{conflict_id}", response_model=ItsmConflictResponse, status_code=201)
async def record_conflict(
    conflict_id: Annotated[str, CONFLICT_ID],
    payload: RecordItsmConflictPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_itsm_idempotency_conflict_manage)
    ],
) -> ItsmConflictResponse:
    now = datetime.now(UTC)
    try:
        kind = ItsmConflictKind(payload.kind)
        field_ownership = ItsmFieldOwnership(payload.field_ownership)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="itsm_conflict_kind_or_ownership_unrecognized",
            title="ITSM idempotency/conflict operation unavailable",
            detail="The conflict kind or field ownership is not recognized.",
        ) from error
    service: ItsmIdempotencyConflictService = request.app.state.itsm_idempotency_conflict_service
    try:
        conflict = await service.record_conflict(
            conflict_id=conflict_id,
            profile_id=payload.profile_id,
            external_record_id=payload.external_record_id,
            kind=kind,
            last_known_source_version=payload.last_known_source_version,
            observed_source_version=payload.observed_source_version,
            field_ownership=field_ownership,
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmIdempotencyConflictError as error:
        _raise(error)
    return ItsmConflictResponse(
        data=_conflict_data(conflict),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/conflicts/{conflict_id}/resolution", response_model=ItsmConflictResponse)
async def resolve_conflict(
    conflict_id: Annotated[str, CONFLICT_ID],
    payload: ResolveItsmConflictPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_itsm_idempotency_conflict_manage)
    ],
) -> ItsmConflictResponse:
    now = datetime.now(UTC)
    service: ItsmIdempotencyConflictService = request.app.state.itsm_idempotency_conflict_service
    try:
        conflict = await service.resolve_conflict(
            conflict_id=conflict_id,
            resolution_summary=payload.resolution_summary,
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmIdempotencyConflictError as error:
        _raise(error)
    return ItsmConflictResponse(
        data=_conflict_data(conflict),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
