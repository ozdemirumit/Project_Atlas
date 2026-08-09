from __future__ import annotations

from datetime import UTC, datetime

from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_REVIEW_REQUEST_CREATE,
    recommendation_review_request_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest, CapabilityClass
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.review_request_ports import (
    RecommendationReviewRequestError,
)


class AuthorizationRecommendationReviewRequestPermissionAuthorizer:
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
            raise RecommendationReviewRequestError(
                "recommendation_review_request_permission_denied"
            )
        decision = await self._service.evaluate(
            AuthorizationRequest(
                subject=actor,
                permission_id=RECOMMENDATION_REVIEW_REQUEST_CREATE,
                resource_type="resource.recommendation.human-review-request",
                scope=recommendation_review_request_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            )
        )
        if not decision.allowed:
            raise RecommendationReviewRequestError(
                "recommendation_review_request_permission_denied"
            )
