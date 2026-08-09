from __future__ import annotations

from datetime import UTC, datetime

from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_READINESS_CREATE,
    recommendation_readiness_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest, CapabilityClass
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.readiness_ports import (
    RecommendationReadinessError,
)


class AuthorizationRecommendationReadinessPermissionAuthorizer:
    def __init__(self, *, service: AuthorizationService, environment: str) -> None:
        self._service = service
        self._environment = environment

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None:
        if (
            actor.organization_id != organization_id
            or environment_id != f"environment.{self._environment}"
        ):
            raise RecommendationReadinessError("recommendation_readiness_permission_denied")
        decision = await self._service.evaluate(
            AuthorizationRequest(
                subject=actor,
                permission_id=RECOMMENDATION_READINESS_CREATE,
                resource_type="resource.recommendation.review-readiness",
                scope=recommendation_readiness_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            )
        )
        if not decision.allowed:
            raise RecommendationReadinessError("recommendation_readiness_permission_denied")
