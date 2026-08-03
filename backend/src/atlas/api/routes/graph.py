from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from atlas.api.errors import AtlasError
from atlas.api.graph_schemas import StorageImpactData, StorageImpactResponse
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_graph_storage_impact_read
from atlas.modules.authorization.application.bootstrap import graph_storage_impact_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.graph.application.engine import GraphImpactError
from atlas.modules.graph.application.service import GraphImpactService, GraphReadContext
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/storage-impact/{entity_id}", response_model=StorageImpactResponse)
async def storage_impact(
    entity_id: str,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_graph_storage_impact_read)],
    max_depth: Annotated[int, Query(ge=1, le=5)] = 5,
) -> StorageImpactResponse:
    now = datetime.now(UTC)
    scope = graph_storage_impact_scope(
        subject.organization_id, request.app.state.settings.environment
    )
    service: GraphImpactService = request.app.state.graph_impact_service
    try:
        result = await service.analyze_storage_impact(
            entity_id=entity_id,
            max_depth=max_depth,
            context=GraphReadContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                assurance_level=subject.assurance_level.value,
                organization_id=scope.organization_id,
                environment_id=scope.environment_id,
                site_id=scope.site_id,
                resource_id=scope.resource_id,
                role_ids=subject.role_ids,
                group_ids=subject.group_ids,
                correlation_id=str(request.state.correlation_id),
                decision_id=decision.decision_id,
                requested_at=now,
            ),
        )
    except GraphImpactError as exc:
        status = 400 if exc.code in {"graph_depth_out_of_range"} else 404
        raise AtlasError(
            status=status,
            code=exc.code,
            title="Graph result unavailable",
            detail=exc.detail,
        ) from exc
    return StorageImpactResponse(
        data=StorageImpactData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=now,
        ),
    )
