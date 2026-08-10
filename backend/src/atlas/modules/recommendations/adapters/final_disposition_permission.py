from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_FINAL_DISPOSITION_CREATE,
    RECOMMENDATION_FINAL_DISPOSITION_READ,
    RECOMMENDATION_PROMOTION_READ,
    RECOMMENDATION_READINESS_READ,
    RECOMMENDATION_REVIEW_REQUEST_READ,
    RECOMMENDATION_TRACK_REVIEW_DECISION_READ,
    recommendation_final_disposition_scope,
    recommendation_promotion_scope,
    recommendation_readiness_scope,
    recommendation_review_request_scope,
    recommendation_track_review_decision_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest, ResourceScope
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.final_disposition_ports import (
    FinalRecommendationDispositionError,
)


class AuthorizationFinalRecommendationDispositionPermissionAuthorizer:
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
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_permission_denied"
            )
        now = datetime.now(UTC)
        requests = (
            self._request(
                actor,
                RECOMMENDATION_FINAL_DISPOSITION_CREATE,
                "resource.recommendation.final-dispositions",
                recommendation_final_disposition_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                RECOMMENDATION_FINAL_DISPOSITION_READ,
                "resource.recommendation.final-dispositions",
                recommendation_final_disposition_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                RECOMMENDATION_TRACK_REVIEW_DECISION_READ,
                "resource.recommendation.track-review-decisions",
                recommendation_track_review_decision_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                RECOMMENDATION_REVIEW_REQUEST_READ,
                "resource.recommendation.human-review-request",
                recommendation_review_request_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                RECOMMENDATION_READINESS_READ,
                "resource.recommendation.review-readiness",
                recommendation_readiness_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                RECOMMENDATION_PROMOTION_READ,
                "resource.recommendation.promotion",
                recommendation_promotion_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
        )
        for request in requests:
            decision = await self._service.evaluate(request)
            if not decision.allowed:
                raise FinalRecommendationDispositionError(
                    "final_recommendation_disposition_permission_denied"
                )

    @staticmethod
    def _request(
        actor: AuthenticatedSubject,
        permission_id: str,
        resource_type: str,
        scope: ResourceScope,
        correlation_id: str,
        requested_at: datetime,
    ) -> AuthorizationRequest:
        return AuthorizationRequest(
            subject=actor,
            permission_id=permission_id,
            resource_type=resource_type,
            scope=scope,
            correlation_id=correlation_id,
            requested_at=requested_at,
        )
