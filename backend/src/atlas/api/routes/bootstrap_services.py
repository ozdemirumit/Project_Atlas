from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.bootstrap_service_schemas import (
    BootstrapServiceDeploymentData,
    BootstrapServiceDeploymentInput,
    BootstrapServiceDeploymentResponse,
    BootstrapServicePlanData,
    BootstrapServicePlanInput,
    BootstrapServicePlanResponse,
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
from atlas.modules.platform.application.bootstrap_service_deployment import (
    BootstrapServiceDeploymentService,
    BootstrapServicePlanService,
)
from atlas.modules.platform.application.bootstrap_service_ports import BootstrapServiceError
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError

router = APIRouter(tags=["bootstrap-services"])
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
        "bootstrap_service_plan_unavailable",
    }:
        status = 404
        detail = "The requested bootstrap service phase is unavailable."
    elif str(code).startswith("bootstrap_"):
        status = 409
        detail = "The service phase cannot run against the current governed state."
    else:
        status = 403
        detail = "The service phase request is not authorized."
    raise AtlasError(
        status=status,
        code=str(code),
        title="Bootstrap service phase unavailable",
        detail=detail,
    ) from error


@router.post(
    "/platform/bootstrap-service-plan/preview",
    response_model=BootstrapServicePlanResponse,
)
async def preview_bootstrap_service_plan(
    payload: BootstrapServicePlanInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_deployment_configuration_preview)
    ],
) -> BootstrapServicePlanResponse:
    service: BootstrapServicePlanService = request.app.state.bootstrap_service_plan_service
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
            data_plan_digest=payload.data_plan_digest,
            migration_artifact_digest=payload.migration_artifact_digest,
        )
    except BootstrapServiceError as error:
        _raise_execution_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapServicePlanResponse(
        data=BootstrapServicePlanData.from_domain(plan),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/platform/bootstrap-state/{run_id}/phases/services",
    response_model=BootstrapServiceDeploymentResponse,
)
async def execute_bootstrap_service_deployment(
    run_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: BootstrapServiceDeploymentInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_state_manage)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> BootstrapServiceDeploymentResponse:
    service: BootstrapServiceDeploymentService = (
        request.app.state.bootstrap_service_deployment_service
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
            data_plan_digest=payload.data_plan_digest,
            migration_artifact_digest=payload.migration_artifact_digest,
            service_schema_version=payload.service_schema_version,
            service_plan_digest=payload.service_plan_digest,
            target_id=payload.target_id,
            expected_target_state=payload.expected_target_state,
            justification=payload.justification,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except (BootstrapRepositoryError, BootstrapServiceError) as error:
        _raise_execution_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapServiceDeploymentResponse(
        data=BootstrapServiceDeploymentData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
