from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.bootstrap_data_schemas import (
    BootstrapDataInitializationData,
    BootstrapDataInitializationInput,
    BootstrapDataInitializationResponse,
    BootstrapDataPlanData,
    BootstrapDataPlanInput,
    BootstrapDataPlanResponse,
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
from atlas.modules.platform.application.bootstrap_data_initialization import (
    BootstrapDataInitializationService,
    BootstrapDataPlanService,
)
from atlas.modules.platform.application.bootstrap_data_ports import BootstrapDataError
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError

router = APIRouter(tags=["bootstrap-data"])
IDEMPOTENCY_HEADER = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise_execution_error(error: Exception) -> NoReturn:
    code = getattr(error, "code", "authorization_denied")
    if code == "bootstrap_idempotency_conflict":
        status = 409
        detail = "The idempotency key is already bound to a different request."
    elif code in {
        "bootstrap_run_unavailable",
        "bootstrap_phase_execution_unavailable",
        "bootstrap_data_plan_unavailable",
    }:
        status = 404
        detail = "The requested bootstrap data phase is unavailable."
    elif code.startswith("bootstrap_"):
        status = 409
        detail = "The data phase cannot run against the current governed state."
    else:
        status = 403
        detail = "The data phase request is not authorized."
    raise AtlasError(
        status=status,
        code=str(code),
        title="Bootstrap data phase unavailable",
        detail=detail,
    ) from error


@router.post(
    "/platform/bootstrap-data-plan/preview",
    response_model=BootstrapDataPlanResponse,
)
async def preview_bootstrap_data_plan(
    payload: BootstrapDataPlanInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_deployment_configuration_preview)
    ],
) -> BootstrapDataPlanResponse:
    service: BootstrapDataPlanService = request.app.state.bootstrap_data_plan_service
    try:
        plan = await service.prepare(
            actor=subject,
            release_id=payload.release_id,
            profile=payload.profile,
            organization_id=payload.organization_id,
            environment_id=payload.environment_id,
            site_id=payload.site_id,
            configuration_digest=payload.configuration_digest,
            overlay=payload.overlay.to_domain(),
            trust_plan_digest=payload.trust_plan_digest,
        )
    except BootstrapDataError as error:
        _raise_execution_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapDataPlanResponse(
        data=BootstrapDataPlanData.from_domain(plan),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/platform/bootstrap-state/{run_id}/phases/data",
    response_model=BootstrapDataInitializationResponse,
)
async def execute_bootstrap_data_initialization(
    run_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: BootstrapDataInitializationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_state_manage)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> BootstrapDataInitializationResponse:
    service: BootstrapDataInitializationService = (
        request.app.state.bootstrap_data_initialization_service
    )
    try:
        result = await service.execute(
            actor=subject,
            lease_holder_id=str(request.state.authenticated_session_id),
            run_id=run_id,
            organization_id=payload.organization_id,
            environment_id=payload.environment_id,
            site_id=payload.site_id,
            expected_version=payload.expected_version,
            plan_digest=payload.plan_digest,
            resume_key=payload.resume_key,
            release_id=payload.release_id,
            profile=payload.profile,
            configuration_digest=payload.configuration_digest,
            overlay=payload.overlay.to_domain(),
            trust_plan_digest=payload.trust_plan_digest,
            data_schema_version=payload.data_schema_version,
            data_plan_digest=payload.data_plan_digest,
            migration_artifact_digest=payload.migration_artifact_digest,
            target_id=payload.target_id,
            expected_target_state=payload.expected_target_state,
            justification=payload.justification,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except (BootstrapRepositoryError, BootstrapDataError) as error:
        _raise_execution_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapDataInitializationResponse(
        data=BootstrapDataInitializationData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
