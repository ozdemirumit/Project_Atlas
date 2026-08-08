from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.ai.application.protected_recommendation_candidate_generation_ports import (
    ProtectedRecommendationCandidateError,
)
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_ANSWER_PRESENTATION_READ,
    AI_PROTECTED_RECOMMENDATION_CANDIDATE_CREATE,
    AI_PROTECTED_RECOMMENDATION_CANDIDATE_READ,
    ai_protected_answer_presentation_scope,
    ai_protected_recommendation_candidate_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest, ResourceScope
from atlas.modules.identity.domain.models import AuthenticatedSubject


class AuthorizationProtectedRecommendationCandidatePermissionAuthorizer:
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
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_permission_denied"
            )
        now = datetime.now(UTC)
        requests = (
            self._request(
                actor,
                AI_PROTECTED_RECOMMENDATION_CANDIDATE_CREATE,
                "resource.ai.protected-recommendation-candidate-set",
                ai_protected_recommendation_candidate_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                AI_PROTECTED_RECOMMENDATION_CANDIDATE_READ,
                "resource.ai.protected-recommendation-candidate-set",
                ai_protected_recommendation_candidate_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                AI_PROTECTED_ANSWER_PRESENTATION_READ,
                "resource.ai.protected-answer-presentation",
                ai_protected_answer_presentation_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
        )
        for request in requests:
            if not (await self._service.evaluate(request)).allowed:
                raise ProtectedRecommendationCandidateError(
                    "protected_recommendation_candidate_permission_denied"
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
