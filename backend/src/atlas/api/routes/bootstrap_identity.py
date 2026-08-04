from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.bootstrap_identity_schemas import (
    BootstrapIdentityHandoffInput,
    BootstrapIdentityHandoffResponse,
    BootstrapIdentityHandoffResultData,
    BootstrapIdentityPlanData,
    BootstrapIdentityPlanInput,
    BootstrapIdentityPlanResponse,
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
from atlas.modules.platform.application.bootstrap_identity_handoff import (
    BootstrapIdentityHandoffService,
    BootstrapIdentityPlanService,
)
from atlas.modules.platform.application.bootstrap_identity_ports import BootstrapIdentityError
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError

router = APIRouter(tags=["bootstrap-identity"])
IDEMPOTENCY_HEADER = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise_error(error: Exception) -> NoReturn:
    code = str(getattr(error, "code", "authorization_denied"))
    status = 404 if code.endswith("unavailable") else 409 if code.startswith("bootstrap_") else 403
    raise AtlasError(
        status=status,
        code=code,
        title="Bootstrap identity phase unavailable",
        detail="The identity handoff cannot run against the current governed state.",
    ) from error


@router.post(
    "/platform/bootstrap-identity-plan/preview", response_model=BootstrapIdentityPlanResponse
)
async def preview_bootstrap_identity_plan(
    payload: BootstrapIdentityPlanInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_deployment_configuration_preview)
    ],
) -> BootstrapIdentityPlanResponse:
    service: BootstrapIdentityPlanService = request.app.state.bootstrap_identity_plan_service
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
            service_plan_digest=payload.service_plan_digest,
        )
    except BootstrapIdentityError as error:
        _raise_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapIdentityPlanResponse(
        data=BootstrapIdentityPlanData.from_domain(plan),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/platform/bootstrap-state/{run_id}/phases/identity",
    response_model=BootstrapIdentityHandoffResponse,
)
async def execute_bootstrap_identity_handoff(
    run_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: BootstrapIdentityHandoffInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_state_manage)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> BootstrapIdentityHandoffResponse:
    service: BootstrapIdentityHandoffService = request.app.state.bootstrap_identity_handoff_service
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
            service_plan_digest=payload.service_plan_digest,
            identity_schema_version=payload.identity_schema_version,
            identity_plan_digest=payload.identity_plan_digest,
            target_id=payload.target_id,
            expected_target_state=payload.expected_target_state,
            justification=payload.justification,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except (BootstrapRepositoryError, BootstrapIdentityError) as error:
        _raise_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapIdentityHandoffResponse(
        data=BootstrapIdentityHandoffResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
