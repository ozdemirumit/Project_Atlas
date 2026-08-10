from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_FINDING_PRESENTATION_CREATE,
    RECOMMENDATION_FINDING_PRESENTATION_READ,
    RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
    RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
    recommendation_finding_presentation_scope,
    recommendation_human_review_finding_scope,
    recommendation_protected_content_scope,
    recommendation_protected_inspection_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.finding_presentation_ports import (
    RecommendationFindingPresentationError,
)


class AuthorizationRecommendationFindingPresentationPermissionAuthorizer:
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
        if environment_id != f"environment.{self._environment}":
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_permission_denied"
            )
        now = datetime.now(UTC)
        requests = (
            AuthorizationRequest(
                subject=actor,
                permission_id=RECOMMENDATION_FINDING_PRESENTATION_CREATE,
                resource_type="resource.recommendation.finding-presentations",
                scope=recommendation_finding_presentation_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id=correlation_id,
                requested_at=now,
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=RECOMMENDATION_FINDING_PRESENTATION_READ,
                resource_type="resource.recommendation.finding-presentations",
                scope=recommendation_finding_presentation_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id=correlation_id,
                requested_at=now,
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
                resource_type="resource.recommendation.human-review-findings",
                scope=recommendation_human_review_finding_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id=correlation_id,
                requested_at=now,
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
                resource_type="resource.recommendation.protected-content",
                scope=recommendation_protected_content_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id=correlation_id,
                requested_at=now,
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
                resource_type="resource.recommendation.protected-inspection",
                scope=recommendation_protected_inspection_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id=correlation_id,
                requested_at=now,
            ),
        )
        for request in requests:
            decision = await self._service.evaluate(request)
            if not decision.allowed:
                raise RecommendationFindingPresentationError(
                    "recommendation_finding_presentation_permission_denied"
                )
