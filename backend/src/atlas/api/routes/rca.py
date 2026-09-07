from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.rca_schemas import (
    RcaCaseData,
    RcaClosePayload,
    RcaCreatePayload,
    RcaResponse,
    RcaReviewPayload,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_rca_close,
    authorize_rca_create,
    authorize_rca_review,
)
from atlas.modules.authorization.application.bootstrap import rca_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.rca.application.service import (
    RcaAccessContext,
    RcaOperationsError,
    RcaService,
)
from atlas.modules.rca.domain.models import RcaCreateRequest, ReviewStatus

router = APIRouter(prefix="/rca", tags=["root-cause-analysis"])


def _raise_rca_error(exc: RcaOperationsError) -> NoReturn:
    status_by_code = {
        "rca_target_unavailable": 404,
        "rca_case_unavailable": 404,
        "rca_review_requires_decision": 422,
        "rca_review_invalid": 422,
        "rca_review_invalid_state": 409,
        "rca_close_invalid_state": 409,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 409),
        code=exc.code,
        title="Root cause analysis unavailable",
        detail=exc.detail,
    ) from exc


@router.post("/storage/{target_id}", response_model=RcaResponse)
async def create_storage_rca(
    target_id: str,
    payload: RcaCreatePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_rca_create)],
) -> RcaResponse:
    now = datetime.now(UTC)
    scope = rca_scope(subject.organization_id, request.app.state.settings.environment)
    service: RcaService = request.app.state.rca_service
    try:
        case = await service.create(
            RcaCreateRequest(
                incident_id=payload.incident_id,
                target_id=target_id,
                user_report=payload.user_report,
                expected_behavior=payload.expected_behavior,
                actual_behavior=payload.actual_behavior,
                window_start=payload.window_start,
                window_end=payload.window_end,
                max_evidence_records=payload.max_evidence_records,
            ),
            context=RcaAccessContext(
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
    except RcaOperationsError as exc:
        status = 404 if exc.code == "rca_target_unavailable" else 409
        raise AtlasError(
            status=status,
            code=exc.code,
            title="Root cause analysis unavailable",
            detail=exc.detail,
        ) from exc
    return RcaResponse(
        data=RcaCaseData.from_domain(case),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/cases/{case_id}/review", response_model=RcaResponse)
async def review_rca_case(
    case_id: str,
    payload: RcaReviewPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_rca_review)],
) -> RcaResponse:
    now = datetime.now(UTC)
    scope = rca_scope(subject.organization_id, request.app.state.settings.environment)
    service: RcaService = request.app.state.rca_service
    try:
        status = ReviewStatus(payload.status)
    except ValueError as exc:
        raise AtlasError(
            status=422,
            code="rca_review_status_invalid",
            title="Root cause analysis unavailable",
            detail="The review status is not recognized.",
        ) from exc
    try:
        case = await service.review(
            case_id,
            version=payload.expected_version,
            reviewer_id=subject.subject_id,
            status=status,
            decision_reason=payload.decision_reason,
            domain_confirmation_criterion=payload.domain_confirmation_criterion,
            context=RcaAccessContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                assurance_level=subject.assurance_level.value,
                organization_id=scope.organization_id,
                environment_id=scope.environment_id,
                site_id=scope.site_id,
                resource_id=scope.resource_id,
                correlation_id=str(request.state.correlation_id),
                decision_id=_decision.decision_id,
                requested_at=now,
            ),
        )
    except RcaOperationsError as exc:
        _raise_rca_error(exc)
    return RcaResponse(
        data=RcaCaseData.from_domain(case),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/cases/{case_id}/close", response_model=RcaResponse)
async def close_rca_case(
    case_id: str,
    payload: RcaClosePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_rca_close)],
) -> RcaResponse:
    now = datetime.now(UTC)
    scope = rca_scope(subject.organization_id, request.app.state.settings.environment)
    service: RcaService = request.app.state.rca_service
    try:
        case = await service.close(
            case_id,
            version=payload.expected_version,
            context=RcaAccessContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                assurance_level=subject.assurance_level.value,
                organization_id=scope.organization_id,
                environment_id=scope.environment_id,
                site_id=scope.site_id,
                resource_id=scope.resource_id,
                correlation_id=str(request.state.correlation_id),
                decision_id=_decision.decision_id,
                requested_at=now,
            ),
        )
    except RcaOperationsError as exc:
        _raise_rca_error(exc)
    return RcaResponse(
        data=RcaCaseData.from_domain(case),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
