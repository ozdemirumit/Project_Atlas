from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from atlas.api.bootstrap_plan_schemas import (
    BootstrapPlanData,
    BootstrapPlanInput,
    BootstrapPlanResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_bootstrap_plan_read
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_plan import (
    BootstrapPlanScopeError,
    BootstrapPlanService,
)

router = APIRouter(prefix="/platform/bootstrap-plan", tags=["bootstrap-plan"])


@router.post("", response_model=BootstrapPlanResponse)
async def build_bootstrap_plan(
    payload: BootstrapPlanInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_plan_read)],
) -> BootstrapPlanResponse:
    service: BootstrapPlanService = request.app.state.bootstrap_plan_service
    try:
        plan = await service.build(
            actor=subject,
            request=payload.to_domain(),
            correlation_id=str(request.state.correlation_id),
        )
    except (ValueError, BootstrapPlanScopeError) as error:
        status = 403 if isinstance(error, BootstrapPlanScopeError) else 422
        raise AtlasError(
            status=status,
            code="authorization_denied" if status == 403 else "request_validation_failed",
            title="Request denied" if status == 403 else "Request validation failed",
            detail="The bootstrap plan request cannot be processed.",
        ) from error
    response.headers["Cache-Control"] = "no-store"
    return BootstrapPlanResponse(
        data=BootstrapPlanData.from_domain(plan),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
