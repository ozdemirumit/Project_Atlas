from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_CREATE,
    KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_READ,
    KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
    operational_knowledge_protected_content_scope,
    operational_knowledge_protected_inspection_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.protected_content_ports import (
    OperationalKnowledgeProtectedContentError,
)


class AuthorizationOperationalKnowledgeProtectedContentPermissionAuthorizer:
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
            raise OperationalKnowledgeProtectedContentError(
                "operational_knowledge_protected_content_permission_denied"
            )
        requests = (
            AuthorizationRequest(
                subject=actor,
                permission_id=KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_CREATE,
                resource_type="resource.knowledge.operational-protected-content",
                scope=operational_knowledge_protected_content_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=KNOWLEDGE_PROTECTED_CONTENT_PRESENTATION_READ,
                resource_type="resource.knowledge.operational-protected-content",
                scope=operational_knowledge_protected_content_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
                resource_type="resource.knowledge.operational-protected-inspections",
                scope=operational_knowledge_protected_inspection_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            ),
        )
        for request in requests:
            decision = await self._service.evaluate(request)
            if not decision.allowed:
                raise OperationalKnowledgeProtectedContentError(
                    "operational_knowledge_protected_content_permission_denied"
                )
