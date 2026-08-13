from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.report_schemas import (
    ItsmHandoffHumanReviewData,
    ItsmHandoffHumanReviewLookupResponse,
    ItsmHandoffHumanReviewResponse,
    ItsmHandoffReviewDecisionPayload,
    ReportCreatePayload,
    TechnicalReportData,
    TechnicalReportResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_itsm_handoff_review_decide,
    authorize_itsm_handoff_review_read,
    authorize_report_create,
    authorize_report_read,
    browser_session_subject,
)
from atlas.core.classification import DataClassification
from atlas.modules.authorization.application.bootstrap import report_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.reports.application.handoff_review_service import (
    ItsmHandoffReviewError,
    ItsmHandoffReviewService,
)
from atlas.modules.reports.application.service import (
    ReportAccessContext,
    ReportOperationsError,
    ReportService,
)
from atlas.modules.reports.domain.handoff_review import ItsmHandoffReviewOutcome
from atlas.modules.reports.domain.models import ReportAudience, ReportRequest, ReportType

router = APIRouter(prefix="/reports", tags=["reports"])


def _raise_handoff_review(error: ItsmHandoffReviewError) -> None:
    status = 404 if error.code == "itsm_handoff_review_not_found" else 409
    if error.code in {
        "itsm_handoff_review_human_required",
        "itsm_handoff_review_assurance_insufficient",
        "itsm_handoff_review_role_required",
        "itsm_handoff_review_separation_required",
    }:
        status = 403
    raise AtlasError(
        status=status,
        code=error.code,
        title="ITSM handoff review unavailable",
        detail="The governed ITSM handoff review could not be completed.",
    ) from error


def _report_context(
    *,
    request: Request,
    subject: AuthenticatedSubject,
    decision: AuthorizationDecision,
    requested_at: datetime,
) -> ReportAccessContext:
    scope = report_scope(subject.organization_id, request.app.state.settings.environment)
    return ReportAccessContext(
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


@router.post("/storage/{target_id}", response_model=TechnicalReportResponse)
async def create_storage_report(
    target_id: str,
    payload: ReportCreatePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_report_create)],
) -> TechnicalReportResponse:
    now = datetime.now(UTC)
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
            context=_report_context(
                request=request, subject=subject, decision=decision, requested_at=now
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


@router.get("/{report_id}", response_model=TechnicalReportResponse)
async def get_technical_report(
    report_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_report_read)],
) -> TechnicalReportResponse:
    now = datetime.now(UTC)
    service: ReportService = request.app.state.report_service
    try:
        report = await service.read(
            report_id=report_id,
            context=_report_context(
                request=request, subject=subject, decision=decision, requested_at=now
            ),
        )
    except ReportOperationsError as exc:
        status = 404 if exc.code == "report_not_found" else 409
        raise AtlasError(
            status=status,
            code=exc.code,
            title="Report unavailable",
            detail=exc.detail,
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    return TechnicalReportResponse(
        data=TechnicalReportData.from_domain(report),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post(
    "/{report_id}/itsm-handoff/reviews",
    response_model=ItsmHandoffHumanReviewResponse,
)
async def decide_itsm_handoff_review(
    report_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ItsmHandoffReviewDecisionPayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_handoff_review_decide)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> ItsmHandoffHumanReviewResponse:
    service: ItsmHandoffReviewService = request.app.state.itsm_handoff_review_service
    try:
        review = await service.decide(
            actor=subject,
            report_id=report_id,
            report_version=payload.report_version,
            report_digest=payload.report_digest,
            handoff_draft_id=payload.handoff_draft_id,
            outcome=ItsmHandoffReviewOutcome(payload.outcome),
            rationale=payload.rationale,
            acknowledged_review_only=payload.acknowledged_review_only,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmHandoffReviewError as error:
        _raise_handoff_review(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmHandoffHumanReviewResponse(
        data=ItsmHandoffHumanReviewData.from_domain(review),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get(
    "/{report_id}/itsm-handoff/review",
    response_model=ItsmHandoffHumanReviewLookupResponse,
)
async def get_itsm_handoff_review(
    report_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    handoff_draft_id: Annotated[str, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_handoff_review_read)],
) -> ItsmHandoffHumanReviewLookupResponse:
    service: ItsmHandoffReviewService = request.app.state.itsm_handoff_review_service
    try:
        review = await service.get_for_handoff(
            actor=subject,
            report_id=report_id,
            handoff_draft_id=handoff_draft_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmHandoffReviewError as error:
        _raise_handoff_review(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmHandoffHumanReviewLookupResponse(
        data=ItsmHandoffHumanReviewData.from_domain(review) if review else None,
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
