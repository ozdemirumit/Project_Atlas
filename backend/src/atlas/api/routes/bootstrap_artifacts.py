from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.bootstrap_artifact_schemas import (
    BootstrapArtifactAcquisitionData,
    BootstrapArtifactAcquisitionInput,
    BootstrapArtifactAcquisitionResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authorize_bootstrap_state_manage, browser_session_subject
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_artifact_acquisition import (
    BootstrapArtifactAcquisitionService,
    BootstrapArtifactExecutionError,
)
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError

router = APIRouter(prefix="/platform/bootstrap-state", tags=["bootstrap-artifacts"])
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
    }:
        status = 404
        detail = "The requested bootstrap phase is unavailable."
    elif code in {
        "bootstrap_stale_revision",
        "bootstrap_plan_mismatch",
        "bootstrap_lease_unavailable",
        "bootstrap_run_completed",
        "bootstrap_phase_out_of_order",
        "bootstrap_phase_in_progress",
        "bootstrap_phase_execution_conflict",
        "bootstrap_artifact_manifest_mismatch",
        "bootstrap_preflight_stale",
        "bootstrap_preflight_failed",
        "bootstrap_preflight_warning_unaccepted",
    }:
        status = 409
        detail = "The artifact phase cannot run against the current governed state."
    else:
        status = 403
        detail = "The artifact phase request is not authorized."
    raise AtlasError(
        status=status,
        code=str(code),
        title="Bootstrap artifact phase unavailable",
        detail=detail,
    ) from error


@router.post(
    "/{run_id}/phases/acquire",
    response_model=BootstrapArtifactAcquisitionResponse,
)
async def execute_artifact_acquisition(
    run_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: BootstrapArtifactAcquisitionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_state_manage)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> BootstrapArtifactAcquisitionResponse:
    service: BootstrapArtifactAcquisitionService = (
        request.app.state.bootstrap_artifact_acquisition_service
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
            manifest_digest=payload.manifest_digest,
            mode=payload.mode,
            profile=payload.profile,
            preflight_report_id=payload.preflight_report_id,
            preflight_state=payload.preflight_state,
            warning_accepted=payload.warning_accepted,
            justification=payload.justification,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except (BootstrapRepositoryError, BootstrapArtifactExecutionError) as error:
        _raise_execution_error(error)
    response.headers["Cache-Control"] = "no-store"
    return BootstrapArtifactAcquisitionResponse(
        data=BootstrapArtifactAcquisitionData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )
