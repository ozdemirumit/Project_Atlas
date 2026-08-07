from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    KNOWLEDGE_FINDING_PRESENTATION_READ,
    KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_READ,
    KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
    KNOWLEDGE_REVIEW_FINDING_READ,
    KNOWLEDGE_TRACK_REVIEW_DECISION_CREATE,
    KNOWLEDGE_TRACK_REVIEW_DECISION_READ,
    operational_knowledge_finding_presentation_scope,
    operational_knowledge_protected_content_scope,
    operational_knowledge_protected_inspection_scope,
    operational_knowledge_review_finding_scope,
    operational_knowledge_track_review_decision_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest, ResourceScope
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.review_decision_ports import (
    OperationalKnowledgeTrackReviewDecisionError,
)


class AuthorizationOperationalKnowledgeTrackReviewDecisionPermissionAuthorizer:
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
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_permission_denied"
            )
        now = datetime.now(UTC)
        requests = (
            self._request(
                actor,
                KNOWLEDGE_TRACK_REVIEW_DECISION_CREATE,
                "resource.knowledge.operational-track-review-decisions",
                operational_knowledge_track_review_decision_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_TRACK_REVIEW_DECISION_READ,
                "resource.knowledge.operational-track-review-decisions",
                operational_knowledge_track_review_decision_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_FINDING_PRESENTATION_READ,
                "resource.knowledge.operational-finding-presentations",
                operational_knowledge_finding_presentation_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_REVIEW_FINDING_READ,
                "resource.knowledge.operational-review-findings",
                operational_knowledge_review_finding_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_READ,
                "resource.knowledge.operational-protected-content",
                operational_knowledge_protected_content_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
                "resource.knowledge.operational-protected-inspections",
                operational_knowledge_protected_inspection_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
        )
        for request in requests:
            decision = await self._service.evaluate(request)
            if not decision.allowed:
                raise OperationalKnowledgeTrackReviewDecisionError(
                    "operational_knowledge_track_review_decision_permission_denied"
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
