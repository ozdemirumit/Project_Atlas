from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.ai.application.protected_candidate_impact_enrichment_ports import (
    ProtectedCandidateImpactError,
)
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_CANDIDATE_IMPACT_CREATE,
    AI_PROTECTED_CANDIDATE_IMPACT_READ,
    AI_PROTECTED_RECOMMENDATION_CANDIDATE_READ,
    GRAPH_STORAGE_IMPACT_READ,
    ai_protected_candidate_impact_scope,
    ai_protected_recommendation_candidate_scope,
    graph_storage_impact_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest, ResourceScope
from atlas.modules.identity.domain.models import AuthenticatedSubject


class AuthorizationProtectedCandidateImpactPermissionAuthorizer:
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
            raise ProtectedCandidateImpactError("protected_candidate_impact_permission_denied")
        now = datetime.now(UTC)
        requests = (
            self._request(
                actor,
                AI_PROTECTED_CANDIDATE_IMPACT_CREATE,
                "resource.ai.protected-candidate-impact-analysis",
                ai_protected_candidate_impact_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                AI_PROTECTED_CANDIDATE_IMPACT_READ,
                "resource.ai.protected-candidate-impact-analysis",
                ai_protected_candidate_impact_scope(
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
                GRAPH_STORAGE_IMPACT_READ,
                "resource.graph.storage-impact",
                graph_storage_impact_scope(organization_id, self._environment),
                correlation_id,
                now,
            ),
        )
        for request in requests:
            if not (await self._service.evaluate(request)).allowed:
                raise ProtectedCandidateImpactError("protected_candidate_impact_permission_denied")

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
