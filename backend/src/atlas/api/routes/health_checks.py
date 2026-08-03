from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.health_check_schemas import (
    HealthCheckOverviewData,
    HealthCheckOverviewResponse,
    HealthCheckRunData,
    HealthCheckRunResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_health_check_overview_read,
    authorize_health_check_run_create,
)
from atlas.modules.authorization.application.bootstrap import health_check_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.health_checks.application.service import (
    HealthCheckAccessContext,
    HealthCheckOperationsError,
    HealthCheckService,
)
from atlas.modules.health_checks.domain.models import HealthCheckTrigger
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/health-checks", tags=["health-checks"])


def _context(
    request: Request,
    subject: AuthenticatedSubject,
    decision: AuthorizationDecision,
    now: datetime,
) -> HealthCheckAccessContext:
    scope = health_check_scope(subject.organization_id, request.app.state.settings.environment)
    return HealthCheckAccessContext(
        subject_id=subject.subject_id,
        actor_type=subject.kind.value,
        authentication_method=subject.authentication_method.value,
        assurance_level=subject.assurance_level.value,
        organization_id=scope.organization_id,
        environment_id=scope.environment_id,
        site_id=scope.site_id,
        resource_id=scope.resource_id,
        correlation_id=str(request.state.correlation_id),
        decision_id=decision.decision_id,
        requested_at=now,
    )


@router.get("/overview", response_model=HealthCheckOverviewResponse)
async def health_check_overview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_health_check_overview_read)],
) -> HealthCheckOverviewResponse:
    now = datetime.now(UTC)
    service: HealthCheckService = request.app.state.health_check_service
    overview = await service.get_overview(_context(request, subject, decision, now))
    return HealthCheckOverviewResponse(
        data=HealthCheckOverviewData.from_domain(overview),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/{definition_id}/runs", response_model=HealthCheckRunResponse)
async def run_health_check(
    definition_id: str,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_health_check_run_create)],
) -> HealthCheckRunResponse:
    now = datetime.now(UTC)
    service: HealthCheckService = request.app.state.health_check_service
    try:
        run = await service.run(
            definition_id,
            trigger=HealthCheckTrigger.MANUAL,
            context=_context(request, subject, decision, now),
        )
    except HealthCheckOperationsError as exc:
        status = 409 if exc.code == "health_check_disabled" else 404
        raise AtlasError(
            status=status,
            code=exc.code,
            title="Health check unavailable",
            detail=exc.detail,
        ) from exc
    return HealthCheckRunResponse(
        data=HealthCheckRunData.from_domain(run),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
