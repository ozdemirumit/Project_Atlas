from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.rca_schemas import RcaCaseData, RcaCreatePayload, RcaResponse
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_rca_create
from atlas.modules.authorization.application.bootstrap import rca_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.rca.application.service import (
    RcaAccessContext,
    RcaOperationsError,
    RcaService,
)
from atlas.modules.rca.domain.models import RcaCreateRequest

router = APIRouter(prefix="/rca", tags=["root-cause-analysis"])


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
