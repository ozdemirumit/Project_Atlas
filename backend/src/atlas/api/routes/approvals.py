from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response

from atlas.api.approval_schemas import (
    ApprovalCreatePayload,
    ApprovalDecisionPayload,
    ApprovalRecordData,
    ApprovalResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_approval_create,
    authorize_approval_decide,
    authorize_approval_read,
)
from atlas.core.capabilities import CapabilityClass
from atlas.modules.approvals.application.service import (
    ApprovalAccessContext,
    ApprovalOperationsError,
    ApprovalService,
)
from atlas.modules.approvals.domain.models import ApprovalCreateRequest, ApprovalOutcome
from atlas.modules.authorization.application.bootstrap import approval_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _context(
    request: Request,
    subject: AuthenticatedSubject,
    decision: AuthorizationDecision,
    now: datetime,
    capability_class: CapabilityClass,
) -> ApprovalAccessContext:
    scope = approval_scope(
        subject.organization_id,
        request.app.state.settings.environment,
        capability_class,
    )
    return ApprovalAccessContext(
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


def _error(exc: ApprovalOperationsError) -> AtlasError:
    if exc.code == "approval_not_found" or exc.code == "approval_source_unavailable":
        status = 404
    elif exc.code in {
        "approval_human_reviewer_required",
        "approval_assurance_insufficient",
        "approval_separation_required",
    }:
        status = 403
    else:
        status = 409
    return AtlasError(
        status=status,
        code=exc.code,
        title="Approval unavailable",
        detail=exc.detail,
    )


@router.post("/storage/{target_id}", response_model=ApprovalResponse, status_code=201)
async def create_approval(
    target_id: str,
    payload: ApprovalCreatePayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_approval_create)],
) -> ApprovalResponse:
    now = datetime.now(UTC)
    service: ApprovalService = request.app.state.approval_service
    try:
        record = await service.create(
            ApprovalCreateRequest(
                recommendation_id=payload.recommendation_id,
                recommendation_version=payload.recommendation_version,
                target_id=target_id,
                option_id=payload.option_id,
                purpose=payload.purpose,
                expires_in_minutes=payload.expires_in_minutes,
            ),
            context=_context(request, subject, decision, now, CapabilityClass.C2_DIAGNOSTIC),
        )
    except ApprovalOperationsError as exc:
        raise _error(exc) from exc
    response.headers["Cache-Control"] = "no-store"
    return ApprovalResponse(
        data=ApprovalRecordData.from_domain(record),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.get("/{request_id}", response_model=ApprovalResponse)
async def get_approval(
    request_id: str,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_approval_read)],
) -> ApprovalResponse:
    now = datetime.now(UTC)
    service: ApprovalService = request.app.state.approval_service
    try:
        record = await service.get(
            request_id,
            context=_context(request, subject, decision, now, CapabilityClass.C0_INFORMATIONAL),
        )
    except ApprovalOperationsError as exc:
        raise _error(exc) from exc
    response.headers["Cache-Control"] = "no-store"
    return ApprovalResponse(
        data=ApprovalRecordData.from_domain(record),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/{request_id}/decisions", response_model=ApprovalResponse)
async def decide_approval(
    request_id: str,
    payload: ApprovalDecisionPayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_approval_decide)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=16, max_length=128),
    ],
) -> ApprovalResponse:
    now = datetime.now(UTC)
    service: ApprovalService = request.app.state.approval_service
    try:
        record = await service.decide(
            request_id,
            outcome=ApprovalOutcome(payload.outcome),
            rationale=payload.rationale,
            expected_version=payload.expected_version,
            idempotency_key=idempotency_key,
            context=_context(request, subject, decision, now, CapabilityClass.C2_DIAGNOSTIC),
        )
    except ApprovalOperationsError as exc:
        raise _error(exc) from exc
    response.headers["Cache-Control"] = "no-store"
    return ApprovalResponse(
        data=ApprovalRecordData.from_domain(record),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
