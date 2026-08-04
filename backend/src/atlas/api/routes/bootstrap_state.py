from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Request, Response

from atlas.api.bootstrap_state_schemas import (
    BootstrapCheckpointInput,
    BootstrapClaimInput,
    BootstrapMutationData,
    BootstrapMutationResponse,
    BootstrapReleaseInput,
    BootstrapStateData,
    BootstrapStateResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_bootstrap_state_manage,
    authorize_bootstrap_state_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_state import (
    BootstrapStateScopeError,
    BootstrapStateService,
)
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError
from atlas.modules.platform.domain.bootstrap_state import BootstrapCheckpointState

router = APIRouter(prefix="/platform/bootstrap-state", tags=["bootstrap-state"])
IDEMPOTENCY_HEADER = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


def _raise_state_error(error: Exception) -> NoReturn:
    code = error.code if isinstance(error, BootstrapRepositoryError) else "authorization_denied"
    if code == "bootstrap_idempotency_conflict":
        status = 409
        detail = "The idempotency key is already bound to a different request."
    elif code in {
        "bootstrap_stale_revision",
        "bootstrap_plan_mismatch",
        "bootstrap_dependency_unsatisfied",
        "bootstrap_phase_out_of_order",
        "bootstrap_lease_unavailable",
        "bootstrap_run_completed",
    }:
        status = 409
        detail = "The requested bootstrap coordination state is unavailable."
    elif code in {"bootstrap_run_unavailable", "bootstrap_phase_unavailable"}:
        status = 404
        detail = "The requested bootstrap coordination state is unavailable."
    else:
        status = 403
        detail = "The bootstrap coordination request is not authorized."
    raise AtlasError(
        status=status,
        code=code,
        title="Bootstrap state unavailable",
        detail=detail,
    ) from error


@router.get("/current", response_model=BootstrapStateResponse)
async def get_current_bootstrap_state(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_state_read)],
) -> BootstrapStateResponse:
    service: BootstrapStateService = request.app.state.bootstrap_state_service
    view = await service.current(
        actor=subject,
        lease_holder_id=getattr(request.state, "authenticated_session_id", None),
        correlation_id=str(request.state.correlation_id),
    )
    response.headers["Cache-Control"] = "no-store"
    return BootstrapStateResponse(data=BootstrapStateData.from_view(view), meta=_meta(request))


@router.post("/claims", response_model=BootstrapMutationResponse, status_code=201)
async def claim_bootstrap_state(
    payload: BootstrapClaimInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_state_manage)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> BootstrapMutationResponse:
    service: BootstrapStateService = request.app.state.bootstrap_state_service
    try:
        result = await service.claim(
            actor=subject,
            lease_holder_id=str(request.state.authenticated_session_id),
            identity=payload.to_identity(),
            lease_duration=timedelta(minutes=payload.lease_minutes),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except (BootstrapRepositoryError, BootstrapStateScopeError) as error:
        _raise_state_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapMutationResponse(
        data=BootstrapMutationData.from_domain(result), meta=_meta(request)
    )


@router.post("/{run_id}/checkpoints", response_model=BootstrapMutationResponse)
async def record_bootstrap_checkpoint(
    run_id: str,
    payload: BootstrapCheckpointInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_state_manage)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> BootstrapMutationResponse:
    service: BootstrapStateService = request.app.state.bootstrap_state_service
    try:
        result = await service.checkpoint(
            actor=subject,
            lease_holder_id=str(request.state.authenticated_session_id),
            run_id=run_id,
            plan_digest=payload.plan_digest,
            resume_key=payload.resume_key,
            phase_id=payload.phase_id,
            state=BootstrapCheckpointState(payload.state),
            safe_output_references=tuple(payload.safe_output_references),
            expected_version=payload.expected_version,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except (BootstrapRepositoryError, BootstrapStateScopeError) as error:
        _raise_state_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapMutationResponse(
        data=BootstrapMutationData.from_domain(result), meta=_meta(request)
    )


@router.post("/{run_id}/release", response_model=BootstrapMutationResponse)
async def release_bootstrap_lease(
    run_id: str,
    payload: BootstrapReleaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_state_manage)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> BootstrapMutationResponse:
    service: BootstrapStateService = request.app.state.bootstrap_state_service
    try:
        result = await service.release(
            actor=subject,
            lease_holder_id=str(request.state.authenticated_session_id),
            run_id=run_id,
            expected_version=payload.expected_version,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except (BootstrapRepositoryError, BootstrapStateScopeError) as error:
        _raise_state_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapMutationResponse(
        data=BootstrapMutationData.from_domain(result), meta=_meta(request)
    )
