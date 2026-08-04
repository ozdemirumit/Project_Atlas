from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.bootstrap_trust_schemas import (
    BootstrapTrustPlanData,
    BootstrapTrustPlanInput,
    BootstrapTrustPlanResponse,
    BootstrapTrustProvisioningData,
    BootstrapTrustProvisioningInput,
    BootstrapTrustProvisioningResponse,
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
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError
from atlas.modules.platform.application.bootstrap_trust_ports import BootstrapTrustError
from atlas.modules.platform.application.bootstrap_trust_provisioning import (
    BootstrapTrustPlanService,
    BootstrapTrustProvisioningService,
)

router = APIRouter(tags=["bootstrap-trust"])
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
        "bootstrap_trust_plan_unavailable",
    }:
        status = 404
        detail = "The requested bootstrap trust phase is unavailable."
    elif code in {
        "bootstrap_stale_revision",
        "bootstrap_plan_mismatch",
        "bootstrap_lease_unavailable",
        "bootstrap_run_completed",
        "bootstrap_phase_out_of_order",
        "bootstrap_phase_in_progress",
        "bootstrap_phase_execution_conflict",
        "bootstrap_configuration_validation_failed",
        "bootstrap_configuration_digest_mismatch",
        "bootstrap_configuration_evidence_missing",
        "bootstrap_trust_schema_mismatch",
        "bootstrap_trust_plan_digest_mismatch",
        "bootstrap_trust_plan_invalid",
    }:
        status = 409
        detail = "The trust phase cannot run against the current governed state."
    else:
        status = 403
        detail = "The trust phase request is not authorized."
    raise AtlasError(
        status=status,
        code=str(code),
        title="Bootstrap trust phase unavailable",
        detail=detail,
    ) from error


@router.post(
    "/platform/bootstrap-trust-plan/preview",
    response_model=BootstrapTrustPlanResponse,
)
async def preview_bootstrap_trust_plan(
    payload: BootstrapTrustPlanInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_deployment_configuration_preview)
    ],
) -> BootstrapTrustPlanResponse:
    service: BootstrapTrustPlanService = request.app.state.bootstrap_trust_plan_service
    try:
        plan = service.prepare(
            actor=subject,
            release_id=payload.release_id,
            profile=payload.profile,
            organization_id=payload.organization_id,
            environment_id=payload.environment_id,
            site_id=payload.site_id,
            configuration_digest=payload.configuration_digest,
            overlay=payload.overlay.to_domain(),
        )
    except BootstrapTrustError as error:
        _raise_execution_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapTrustPlanResponse(
        data=BootstrapTrustPlanData.from_domain(plan),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.post(
    "/platform/bootstrap-state/{run_id}/phases/trust",
    response_model=BootstrapTrustProvisioningResponse,
)
async def execute_bootstrap_trust_provisioning(
    run_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: BootstrapTrustProvisioningInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_state_manage)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> BootstrapTrustProvisioningResponse:
    service: BootstrapTrustProvisioningService = (
        request.app.state.bootstrap_trust_provisioning_service
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
            trust_schema_version=payload.trust_schema_version,
            trust_plan_digest=payload.trust_plan_digest,
            justification=payload.justification,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except (BootstrapRepositoryError, BootstrapTrustError) as error:
        _raise_execution_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapTrustProvisioningResponse(
        data=BootstrapTrustProvisioningData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )
