from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.bootstrap_handoff_schemas import (
    BootstrapHandoffInput,
    BootstrapHandoffPlanData,
    BootstrapHandoffPlanInput,
    BootstrapHandoffPlanResponse,
    BootstrapHandoffResponse,
    BootstrapHandoffResultData,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_bootstrap_state_manage,
    authorize_deployment_configuration_preview,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_handoff_ports import (
    BootstrapHandoffError,
)
from atlas.modules.platform.application.bootstrap_operational_handoff import (
    BootstrapHandoffPlanService,
    BootstrapOperationalHandoffService,
)
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError

router = APIRouter(tags=["bootstrap-handoff"])
IDEMPOTENCY_HEADER = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise_error(error: Exception) -> NoReturn:
    code = str(getattr(error, "code", "authorization_denied"))
    status = 404 if code.endswith("unavailable") else 409 if code.startswith("bootstrap_") else 403
    raise AtlasError(
        status=status,
        code=code,
        title="Bootstrap handoff phase unavailable",
        detail="Operational handoff cannot run against the current governed state.",
    ) from error


@router.post(
    "/platform/bootstrap-handoff-plan/preview",
    response_model=BootstrapHandoffPlanResponse,
)
async def preview_bootstrap_handoff_plan(
    payload: BootstrapHandoffPlanInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_deployment_configuration_preview)
    ],
) -> BootstrapHandoffPlanResponse:
    service: BootstrapHandoffPlanService = request.app.state.bootstrap_handoff_plan_service
    try:
        plan = await service.prepare(
            actor=subject, **payload.model_dump(exclude={"schema_version"})
        )
    except BootstrapHandoffError as error:
        _raise_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapHandoffPlanResponse(
        data=BootstrapHandoffPlanData.from_domain(plan),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/platform/bootstrap-state/{run_id}/phases/handoff",
    response_model=BootstrapHandoffResponse,
)
async def execute_bootstrap_handoff(
    run_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: BootstrapHandoffInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_state_manage)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> BootstrapHandoffResponse:
    service: BootstrapOperationalHandoffService = (
        request.app.state.bootstrap_operational_handoff_service
    )
    try:
        result = await service.execute(
            actor=subject,
            lease_holder_id=str(request.state.authenticated_session_id),
            run_id=run_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version", "phase_id"}),
        )
    except (BootstrapRepositoryError, BootstrapHandoffError) as error:
        _raise_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapHandoffResponse(
        data=BootstrapHandoffResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
