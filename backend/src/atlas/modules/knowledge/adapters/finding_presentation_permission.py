from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    KNOWLEDGE_FINDING_PRESENTATION_CREATE,
    KNOWLEDGE_FINDING_PRESENTATION_READ,
    KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_READ,
    KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
    KNOWLEDGE_REVIEW_FINDING_READ,
    operational_knowledge_finding_presentation_scope,
    operational_knowledge_protected_content_scope,
    operational_knowledge_protected_inspection_scope,
    operational_knowledge_review_finding_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.finding_presentation_ports import (
    OperationalKnowledgeFindingPresentationError,
)


class AuthorizationOperationalKnowledgeFindingPresentationPermissionAuthorizer:
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
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_permission_denied"
            )
        now = datetime.now(UTC)
        requests = (
            AuthorizationRequest(
                subject=actor,
                permission_id=KNOWLEDGE_FINDING_PRESENTATION_CREATE,
                resource_type="resource.knowledge.operational-finding-presentations",
                scope=operational_knowledge_finding_presentation_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id=correlation_id,
                requested_at=now,
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=KNOWLEDGE_FINDING_PRESENTATION_READ,
                resource_type="resource.knowledge.operational-finding-presentations",
                scope=operational_knowledge_finding_presentation_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id=correlation_id,
                requested_at=now,
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=KNOWLEDGE_REVIEW_FINDING_READ,
                resource_type="resource.knowledge.operational-review-findings",
                scope=operational_knowledge_review_finding_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id=correlation_id,
                requested_at=now,
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_READ,
                resource_type="resource.knowledge.operational-protected-content",
                scope=operational_knowledge_protected_content_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id=correlation_id,
                requested_at=now,
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
                resource_type="resource.knowledge.operational-protected-inspections",
                scope=operational_knowledge_protected_inspection_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id=correlation_id,
                requested_at=now,
            ),
        )
        for request in requests:
            decision = await self._service.evaluate(request)
            if not decision.allowed:
                raise OperationalKnowledgeFindingPresentationError(
                    "operational_knowledge_finding_presentation_permission_denied"
                )
