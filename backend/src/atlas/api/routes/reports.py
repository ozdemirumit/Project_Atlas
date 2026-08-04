from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.report_schemas import (
    ReportCreatePayload,
    TechnicalReportData,
    TechnicalReportResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_report_create
from atlas.core.classification import DataClassification
from atlas.modules.authorization.application.bootstrap import report_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.reports.application.service import (
    ReportAccessContext,
    ReportOperationsError,
    ReportService,
)
from atlas.modules.reports.domain.models import ReportAudience, ReportRequest, ReportType

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/storage/{target_id}", response_model=TechnicalReportResponse)
async def create_storage_report(
    target_id: str,
    payload: ReportCreatePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_report_create)],
) -> TechnicalReportResponse:
    now = datetime.now(UTC)
    scope = report_scope(subject.organization_id, request.app.state.settings.environment)
    service: ReportService = request.app.state.report_service
    try:
        report = await service.create(
            ReportRequest(
                source_recommendation_id=payload.source_recommendation_id,
                source_recommendation_version=payload.source_recommendation_version,
                target_id=target_id,
                report_type=ReportType(payload.report_type),
                audience=ReportAudience(payload.audience),
                classification=DataClassification(payload.classification),
                include_itsm_handoff=payload.include_itsm_handoff,
                incident_reference=payload.incident_reference,
            ),
            context=ReportAccessContext(
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
            ),
        )
    except ReportOperationsError as exc:
        status = 404 if exc.code == "report_source_unavailable" else 409
        raise AtlasError(
            status=status,
            code=exc.code,
            title="Report unavailable",
            detail=exc.detail,
        ) from exc
    return TechnicalReportResponse(
        data=TechnicalReportData.from_domain(report),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
