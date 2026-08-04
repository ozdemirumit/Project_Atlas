from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_security_export_overview_read,
    authorize_security_export_test_create,
)
from atlas.api.security_export_schemas import (
    DeliveryRecordData,
    SecurityExportOverviewData,
    SecurityExportOverviewResponse,
    SecurityExportTestResponse,
)
from atlas.modules.authorization.application.bootstrap import security_export_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.security_export.application.service import (
    SecurityExportAccessContext,
    SecurityExportOperationsError,
    SecurityExportService,
)

router = APIRouter(prefix="/security-export", tags=["security-export"])


def _context(
    request: Request,
    subject: AuthenticatedSubject,
    decision: AuthorizationDecision,
    requested_at: datetime,
) -> SecurityExportAccessContext:
    scope = security_export_scope(subject.organization_id, request.app.state.settings.environment)
    return SecurityExportAccessContext(
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
        requested_at=requested_at,
    )


@router.get("/overview", response_model=SecurityExportOverviewResponse)
async def get_security_export_overview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_security_export_overview_read)],
) -> SecurityExportOverviewResponse:
    now = datetime.now(UTC)
    service: SecurityExportService = request.app.state.security_export_service
    try:
        overview = await service.get_overview(context=_context(request, subject, decision, now))
    except SecurityExportOperationsError as exc:
        raise AtlasError(
            status=409,
            code=exc.code,
            title="Security export unavailable",
            detail=exc.detail,
        ) from exc
    return SecurityExportOverviewResponse(
        data=SecurityExportOverviewData.from_domain(overview),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/test-event", response_model=SecurityExportTestResponse)
async def create_security_export_test_event(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_security_export_test_create)],
) -> SecurityExportTestResponse:
    now = datetime.now(UTC)
    service: SecurityExportService = request.app.state.security_export_service
    try:
        delivery = await service.emit_test_event(context=_context(request, subject, decision, now))
    except SecurityExportOperationsError as exc:
        raise AtlasError(
            status=409,
            code=exc.code,
            title="Security export test unavailable",
            detail=exc.detail,
        ) from exc
    return SecurityExportTestResponse(
        data=DeliveryRecordData.from_domain(delivery),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
