from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_upgrade_readiness,
    authorize_upgrade_simulation,
    browser_session_subject,
)
from atlas.api.upgrade_schemas import (
    UpgradeReadinessData,
    UpgradeReadinessInput,
    UpgradeReadinessResponse,
    UpgradeSimulationData,
    UpgradeSimulationInput,
    UpgradeSimulationResponse,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.upgrade.application.ports import UpgradeError
from atlas.modules.upgrade.application.service import UpgradeService

router = APIRouter(prefix="/platform/upgrades", tags=["upgrade-simulation"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key",
    min_length=8,
    max_length=128,
    pattern=r"^[A-Za-z0-9._:-]+$",
)


def _raise(error: UpgradeError) -> NoReturn:
    status = 404 if error.code.endswith("unavailable") else 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="Upgrade simulation unavailable",
        detail=(
            "The bounded upgrade readiness or isolated rollback simulation cannot proceed safely."
        ),
    ) from error


@router.post("/readiness-preview", response_model=UpgradeReadinessResponse)
async def preview_upgrade_readiness(
    payload: UpgradeReadinessInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_upgrade_readiness)],
) -> UpgradeReadinessResponse:
    service: UpgradeService = request.app.state.upgrade_service
    try:
        result = await service.preview(
            actor=subject, **payload.model_dump(exclude={"schema_version"})
        )
    except UpgradeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return UpgradeReadinessResponse(
        data=UpgradeReadinessData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("/{source_run_id}/simulations", response_model=UpgradeSimulationResponse)
async def simulate_upgrade_rollback(
    source_run_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: UpgradeSimulationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_upgrade_simulation)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> UpgradeSimulationResponse:
    service: UpgradeService = request.app.state.upgrade_service
    try:
        result = await service.simulate(
            actor=subject,
            source_run_id=source_run_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except UpgradeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return UpgradeSimulationResponse(
        data=UpgradeSimulationData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
