from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Query, Request, Response

from atlas.api.audit_export_schemas import (
    AuditExportOverviewData,
    AuditExportOverviewResponse,
    AuditRetryData,
    AuditRetryResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_audit_export,
    authorize_audit_read,
    browser_session_subject,
)
from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import audit_export_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.security_export.application.service import (
    SecurityExportAccessContext,
    SecurityExportOperationsError,
    SecurityExportService,
)

router = APIRouter(prefix="/audit-export", tags=["audit-export"])


def _context(
    request: Request,
    subject: AuthenticatedSubject,
    decision: AuthorizationDecision,
    requested_at: datetime,
) -> SecurityExportAccessContext:
    scope = audit_export_scope(
        subject.organization_id,
        request.app.state.settings.environment,
        CapabilityClass.C0_INFORMATIONAL,
    )
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


def _raise_request_error(exc: SecurityExportOperationsError) -> NoReturn:
    raise AtlasError(
        status=400,
        code=exc.code,
        title="Audit export request unavailable",
        detail="The bounded audit request could not be processed.",
    ) from exc


@router.get("/overview", response_model=AuditExportOverviewResponse)
async def get_audit_export_overview(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_audit_read)],
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    query: Annotated[str | None, Query(max_length=80)] = None,
    outcome: Annotated[str | None, Query(max_length=80)] = None,
) -> AuditExportOverviewResponse:
    now = datetime.now(UTC)
    response.headers["Cache-Control"] = "no-store"
    service: SecurityExportService = request.app.state.security_export_service
    try:
        overview = await service.get_audit_overview(
            context=_context(request, subject, decision, now),
            limit=limit,
            cursor=cursor,
            query=query,
            outcome=outcome,
        )
    except SecurityExportOperationsError as exc:
        _raise_request_error(exc)
    return AuditExportOverviewResponse(
        data=AuditExportOverviewData.from_domain(overview),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/retry", response_model=AuditRetryResponse)
async def retry_audit_export_deliveries(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_audit_export)],
) -> AuditRetryResponse:
    now = datetime.now(UTC)
    response.headers["Cache-Control"] = "no-store"
    service: SecurityExportService = request.app.state.security_export_service
    try:
        result = await service.retry_audit_deliveries(
            context=_context(request, subject, decision, now)
        )
    except SecurityExportOperationsError as exc:
        _raise_request_error(exc)
    return AuditRetryResponse(
        data=AuditRetryData.from_domain(result),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
