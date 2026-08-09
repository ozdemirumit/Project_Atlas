from __future__ import annotations

from datetime import UTC, datetime

from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE,
    RECOMMENDATION_REVIEWER_ASSIGNMENT_READ,
    recommendation_reviewer_assignment_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest, CapabilityClass
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.reviewer_assignment_ports import (
    RecommendationReviewerAssignmentError,
)


class AuthorizationRecommendationReviewerAssignmentPermissionAuthorizer:
    def __init__(self, *, service: AuthorizationService, environment: str) -> None:
        self._service = service
        self._environment = environment

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        permission_id: str,
        correlation_id: str,
    ) -> None:
        if (
            actor.organization_id != organization_id
            or environment_id != f"environment.{self._environment}"
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_permission_denied"
            )
        capability_class = (
            CapabilityClass.C3_CONTROLLED_CHANGE
            if permission_id == RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE
            else CapabilityClass.C1_READ_ONLY
            if permission_id == RECOMMENDATION_REVIEWER_ASSIGNMENT_READ
            else None
        )
        if capability_class is None:
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_permission_denied"
            )
        decision = await self._service.evaluate(
            AuthorizationRequest(
                subject=actor,
                permission_id=permission_id,
                resource_type="resource.recommendation.reviewer-assignment",
                scope=recommendation_reviewer_assignment_scope(
                    organization_id,
                    self._environment,
                    capability_class,
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            )
        )
        if not decision.allowed:
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_permission_denied"
            )
