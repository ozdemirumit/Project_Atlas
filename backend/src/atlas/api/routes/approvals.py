from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from atlas.api.approval_schemas import (
    ApprovalCreatePayload,
    ApprovalDecisionPayload,
    ApprovalListData,
    ApprovalListResponse,
    ApprovalRecordData,
    ApprovalResponse,
    ApprovalWithdrawalPayload,
    ItsmExternalApprovalBindingInput,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_approval_cancel,
    authorize_approval_create,
    authorize_approval_decide,
    authorize_approval_read,
    authorize_approval_revoke,
)
from atlas.core.capabilities import CapabilityClass
from atlas.modules.approvals.application.service import (
    ApprovalAccessContext,
    ApprovalOperationsError,
    ApprovalService,
)
from atlas.modules.approvals.domain.models import (
    ApprovalCreateRequest,
    ApprovalOutcome,
    ApprovalState,
)
from atlas.modules.approvals.domain.stages import ApprovalStageRequirement
from atlas.modules.authorization.application.bootstrap import approval_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.itsm.domain.approval_sync import ItsmExternalApprovalBinding

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
        role_ids=subject.role_ids,
    )


def _error(exc: ApprovalOperationsError) -> AtlasError:
    if exc.code == "approval_not_found" or exc.code == "approval_source_unavailable":
        status = 404
    elif exc.code in {
        "approval_human_reviewer_required",
        "approval_assurance_insufficient",
        "approval_separation_required",
        "approval_cancel_not_requester",
        "approval_stage_role_mismatch",
        "approval_list_owner_forbidden",
        "approval_list_role_forbidden",
    }:
        status = 403
    elif exc.code in {
        "approval_rationale_required",
        "approval_wrong_operation",
        "approval_itsm_binding_mismatch",
        "approval_stage_required",
        "approval_stage_unknown",
        "approval_stage_plan_invalid",
        "approval_list_limit_invalid",
        "approval_list_cursor_invalid",
    }:
        status = 422
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
    stage_requirements: tuple[ApprovalStageRequirement, ...] | None = None
    if payload.stage_requirements is not None:
        try:
            stage_requirements = tuple(
                ApprovalStageRequirement(
                    stage_id=item.stage_id,
                    required_role=item.required_role,
                    required_scope_reference=item.required_scope_reference,
                    sequence=item.sequence,
                    quorum=item.quorum,
                    expiry_minutes=item.expiry_minutes,
                )
                for item in payload.stage_requirements
            )
        except ValueError as exc:
            raise AtlasError(
                status=422,
                code="approval_stage_plan_invalid",
                title="Approval unavailable",
                detail="The requested approval stage plan is invalid.",
            ) from exc
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
            stage_requirements=stage_requirements,
        )
    except ApprovalOperationsError as exc:
        raise _error(exc) from exc
    response.headers["Cache-Control"] = "no-store"
    return ApprovalResponse(
        data=ApprovalRecordData.from_domain(record),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.get("", response_model=ApprovalListResponse)
async def list_approvals(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_approval_read)],
    state: Annotated[
        str | None,
        Query(
            pattern=(
                r"^(pending|partially_approved|approved|rejected|needs_evidence|deferred"
                r"|expired|revoked|cancelled)$"
            )
        ),
    ] = None,
    role_id: Annotated[str | None, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")] = None,
    scope_reference: Annotated[str | None, Query(max_length=400)] = None,
    owner_subject_id: Annotated[str | None, Query(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")] = None,
    expiring_before: Annotated[datetime | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApprovalListResponse:
    """docs/037_Approval_Workflow.md SS22/SS29: the real, RBAC-gated approval inbox -- lists
    requests the caller owns or is currently eligible to decide, filterable by state, role,
    scope, owner, and expiry, cursor-paginated. See `ApprovalService.list()` for the full
    visibility and filtering contract."""
    now = datetime.now(UTC)
    service: ApprovalService = request.app.state.approval_service
    try:
        records, next_cursor = await service.list(
            context=_context(request, subject, decision, now, CapabilityClass.C0_INFORMATIONAL),
            state=ApprovalState(state) if state is not None else None,
            role_id=role_id,
            scope_reference=scope_reference,
            owner_subject_id=owner_subject_id,
            expiring_before=expiring_before,
            cursor=cursor,
            limit=limit,
            correlation_id=str(request.state.correlation_id),
        )
    except ApprovalOperationsError as exc:
        raise _error(exc) from exc
    response.headers["Cache-Control"] = "no-store"
    return ApprovalListResponse(
        data=ApprovalListData(
            items=[ApprovalRecordData.from_domain(record) for record in records],
            next_cursor=next_cursor,
            limit=limit,
        ),
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
            stage_id=payload.stage_id,
        )
    except ApprovalOperationsError as exc:
        raise _error(exc) from exc
    response.headers["Cache-Control"] = "no-store"
    return ApprovalResponse(
        data=ApprovalRecordData.from_domain(record),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/{request_id}/cancel", response_model=ApprovalResponse)
async def cancel_approval(
    request_id: str,
    payload: ApprovalWithdrawalPayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_approval_cancel)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=16, max_length=128),
    ],
) -> ApprovalResponse:
    now = datetime.now(UTC)
    service: ApprovalService = request.app.state.approval_service
    try:
        record = await service.cancel(
            request_id,
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


@router.post("/{request_id}/revoke", response_model=ApprovalResponse)
async def revoke_approval(
    request_id: str,
    payload: ApprovalWithdrawalPayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_approval_revoke)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=16, max_length=128),
    ],
) -> ApprovalResponse:
    now = datetime.now(UTC)
    service: ApprovalService = request.app.state.approval_service
    try:
        record = await service.revoke(
            request_id,
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


@router.post("/{request_id}/itsm-binding", response_model=ApprovalResponse)
async def attach_itsm_binding(
    request_id: str,
    payload: ItsmExternalApprovalBindingInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_approval_decide)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=16, max_length=128),
    ],
) -> ApprovalResponse:
    """ATLAS-036 SS12: admits one validated external ITSM approval as an input to this
    request's own approval contract -- never a substitute for it (ATLAS-037 remains
    authoritative). Only attachable while the request is still pending."""
    now = datetime.now(UTC)
    service: ApprovalService = request.app.state.approval_service
    try:
        binding = ItsmExternalApprovalBinding(
            binding_id=payload.binding_id,
            profile_id=payload.profile_id,
            external_approval_record_id=payload.external_approval_record_id,
            external_record_version=payload.external_record_version,
            eligible_approver_reference=payload.eligible_approver_reference,
            approving_subject_reference=payload.approving_subject_reference,
            exact_plan_reference=payload.exact_plan_reference,
            exact_plan_version=payload.exact_plan_version,
            validated_at=now,
            atlas_approval_reference=request_id,
        )
    except ValueError as exc:
        raise AtlasError(
            status=422,
            code="approval_itsm_binding_invalid",
            title="Approval unavailable",
            detail="The requested ITSM approval binding is invalid.",
        ) from exc
    try:
        record = await service.attach_itsm_binding(
            request_id,
            binding,
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
