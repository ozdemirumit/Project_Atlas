from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import document_knowledge_scope
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.document_knowledge_ports import DocumentKnowledgeError


class AuthorizationDocumentKnowledgePermissionAuthorizer:
    """One reusable authorizer for every stage of the compact document chain.

    Deliberately not one dedicated class per stage (unlike the Operational chain's
    convention) — the four stages share the same resource family and capability class;
    only the permission_id differs. See ADR-184.
    """

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
        if environment_id != f"environment.{self._environment}":
            raise DocumentKnowledgeError(
                "document_knowledge_permission_denied", "Environment scope mismatch."
            )
        capability_class = (
            CapabilityClass.C1_READ_ONLY
            if permission_id.endswith(".read")
            else CapabilityClass.C2_DIAGNOSTIC
        )
        request = AuthorizationRequest(
            subject=actor,
            permission_id=permission_id,
            resource_type="resource.knowledge.document-governance",
            scope=document_knowledge_scope(organization_id, self._environment, capability_class),
            correlation_id=correlation_id,
            requested_at=datetime.now(UTC),
        )
        decision = await self._service.evaluate(request)
        if not decision.allowed:
            raise DocumentKnowledgeError(
                "document_knowledge_permission_denied", "Authorization was denied."
            )
