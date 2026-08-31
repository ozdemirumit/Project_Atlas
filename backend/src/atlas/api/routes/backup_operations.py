from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from atlas.api.backup_operations_schemas import BackupOverviewData, BackupOverviewResponse
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_backup_overview_read
from atlas.modules.authorization.application.bootstrap import backup_overview_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.backup_operations.application.service import (
    BackupOperationsService,
    BackupReadContext,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/backup", tags=["backup"])


@router.get("/overview", response_model=BackupOverviewResponse)
async def backup_overview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_backup_overview_read)],
) -> BackupOverviewResponse:
    now = datetime.now(UTC)
    scope = backup_overview_scope(subject.organization_id, request.app.state.settings.environment)
    service: BackupOperationsService = request.app.state.backup_operations_service
    overview = await service.get_overview(
        BackupReadContext(
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
    return BackupOverviewResponse(
        data=BackupOverviewData.from_domain(overview),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=now,
        ),
    )
