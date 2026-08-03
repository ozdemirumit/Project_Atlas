from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.investigation_schemas import (
    InvestigationCreateRequest,
    InvestigationResponse,
    ReasoningArtifactData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_investigation_create
from atlas.modules.authorization.application.bootstrap import investigation_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.investigations.application.service import (
    InvestigationAccessContext,
    InvestigationOperationsError,
    InvestigationService,
)
from atlas.modules.investigations.domain.models import InvestigationRequest

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.post("/storage/{target_id}", response_model=InvestigationResponse)
async def create_storage_investigation(
    target_id: str,
    payload: InvestigationCreateRequest,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_investigation_create)],
) -> InvestigationResponse:
    now = datetime.now(UTC)
    scope = investigation_scope(subject.organization_id, request.app.state.settings.environment)
    service: InvestigationService = request.app.state.investigation_service
    try:
        artifact = await service.create(
            InvestigationRequest(
                target_id=target_id,
                question=payload.question,
                intended_decision=payload.intended_decision,
                window_start=payload.window_start,
                window_end=payload.window_end,
                max_evidence_records=payload.max_evidence_records,
            ),
            context=InvestigationAccessContext(
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
    except InvestigationOperationsError as exc:
        status = 404 if exc.code == "investigation_target_unavailable" else 409
        raise AtlasError(
            status=status,
            code=exc.code,
            title="Investigation unavailable",
            detail=exc.detail,
        ) from exc
    return InvestigationResponse(
        data=ReasoningArtifactData.from_domain(artifact),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
