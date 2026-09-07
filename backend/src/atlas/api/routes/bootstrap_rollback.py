from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.bootstrap_rollback_schemas import (
    BootstrapRollbackAttemptData,
    BootstrapRollbackAttemptInput,
    BootstrapRollbackAttemptResponse,
    BootstrapRollbackPlanData,
    BootstrapRollbackPlanInput,
    BootstrapRollbackPlanResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_bootstrap_rollback_manage
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_rollback import (
    BootstrapRollbackError,
    BootstrapRollbackService,
)

router = APIRouter(prefix="/platform/bootstrap-rollback", tags=["bootstrap-rollback"])
PLAN_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


def _raise(exc: BootstrapRollbackError) -> NoReturn:
    status_by_code = {
        "bootstrap_rollback_plan_invalid": 422,
        "bootstrap_rollback_plan_unavailable": 404,
        "bootstrap_rollback_not_permitted": 409,
        "bootstrap_rollback_attempt_invalid": 422,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 400),
        code=exc.code,
        title="Bootstrap rollback unavailable",
        detail="The requested bootstrap rollback operation could not be completed.",
    ) from exc


@router.post("/plans", response_model=BootstrapRollbackPlanResponse, status_code=201)
async def plan_bootstrap_rollback(
    payload: BootstrapRollbackPlanInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_rollback_manage)],
) -> BootstrapRollbackPlanResponse:
    service: BootstrapRollbackService = request.app.state.bootstrap_rollback_service
    try:
        plan = await service.plan_rollback(
            plan_id=payload.plan_id,
            release_id=payload.release_id,
            target_release_id=payload.target_release_id,
            support=payload.support.to_domain(),
            schema_check=payload.schema_check.to_domain(),
            component_compatibility=tuple(
                item.to_domain() for item in payload.component_compatibility
            ),
            configuration_rollback_independent=payload.configuration_rollback_independent,
            secret_rollback_independent=payload.secret_rollback_independent,
            artifacts_available_until=payload.artifacts_available_until,
            correlation_id=str(request.state.correlation_id),
        )
    except BootstrapRollbackError as exc:
        _raise(exc)
    return BootstrapRollbackPlanResponse(
        data=BootstrapRollbackPlanData.from_domain(plan), meta=_meta(request)
    )


@router.post(
    "/plans/{plan_id}/attempts", response_model=BootstrapRollbackAttemptResponse, status_code=201
)
async def record_bootstrap_rollback_attempt(
    plan_id: Annotated[str, PLAN_ID],
    payload: BootstrapRollbackAttemptInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_rollback_manage)],
) -> BootstrapRollbackAttemptResponse:
    service: BootstrapRollbackService = request.app.state.bootstrap_rollback_service
    try:
        attempt = await service.record_attempt(
            attempt_id=payload.attempt_id,
            plan_id=plan_id,
            started_at=payload.started_at,
            outcome=payload.outcome,
            post_rollback_health_check_passed=payload.post_rollback_health_check_passed,
            post_rollback_security_check_passed=payload.post_rollback_security_check_passed,
            failure_recovery_reference=payload.failure_recovery_reference,
            correlation_id=str(request.state.correlation_id),
        )
    except BootstrapRollbackError as exc:
        _raise(exc)
    return BootstrapRollbackAttemptResponse(
        data=BootstrapRollbackAttemptData.from_domain(attempt), meta=_meta(request)
    )
