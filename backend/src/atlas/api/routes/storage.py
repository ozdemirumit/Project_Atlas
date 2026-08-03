from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_storage_overview_read
from atlas.api.storage_schemas import StorageOverviewData, StorageOverviewResponse
from atlas.modules.authorization.application.bootstrap import storage_overview_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.storage.application.service import StorageOperationsService, StorageReadContext

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/overview", response_model=StorageOverviewResponse)
async def storage_overview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_storage_overview_read)],
) -> StorageOverviewResponse:
    now = datetime.now(UTC)
    scope = storage_overview_scope(subject.organization_id, request.app.state.settings.environment)
    service: StorageOperationsService = request.app.state.storage_operations_service
    overview = await service.get_overview(
        StorageReadContext(
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
    )
    return StorageOverviewResponse(
        data=StorageOverviewData.from_domain(overview),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=now,
        ),
    )
