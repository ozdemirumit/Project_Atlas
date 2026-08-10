from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE,
    RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
    RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
    recommendation_human_review_finding_scope,
    recommendation_protected_content_scope,
    recommendation_protected_inspection_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.human_review_finding_ports import (
    RecommendationHumanReviewFindingError,
)


class AuthorizationRecommendationHumanReviewFindingPermissionAuthorizer:
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
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_permission_denied"
            )
        requests = (
            AuthorizationRequest(
                subject=actor,
                permission_id=RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE,
                resource_type="resource.recommendation.human-review-findings",
                scope=recommendation_human_review_finding_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
                resource_type="resource.recommendation.human-review-findings",
                scope=recommendation_human_review_finding_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
                resource_type="resource.recommendation.protected-content",
                scope=recommendation_protected_content_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
                resource_type="resource.recommendation.protected-inspection",
                scope=recommendation_protected_inspection_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            ),
        )
        for request in requests:
            decision = await self._service.evaluate(request)
            if not decision.allowed:
                raise RecommendationHumanReviewFindingError(
                    "recommendation_human_review_finding_permission_denied"
                )
