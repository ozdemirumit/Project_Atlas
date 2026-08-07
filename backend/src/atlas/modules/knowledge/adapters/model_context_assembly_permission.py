from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_MODEL_CONTEXT_CREATE,
    AI_PROTECTED_MODEL_CONTEXT_READ,
    KNOWLEDGE_PROTECTED_RETRIEVAL_READ,
    ai_protected_model_context_scope,
    operational_knowledge_protected_retrieval_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest, ResourceScope
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.model_context_assembly_ports import (
    ProtectedModelContextError,
)


class AuthorizationProtectedModelContextPermissionAuthorizer:
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
            raise ProtectedModelContextError("protected_model_context_permission_denied")
        now = datetime.now(UTC)
        requests = (
            self._request(
                actor,
                AI_PROTECTED_MODEL_CONTEXT_CREATE,
                "resource.ai.protected-model-context",
                ai_protected_model_context_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                AI_PROTECTED_MODEL_CONTEXT_READ,
                "resource.ai.protected-model-context",
                ai_protected_model_context_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_PROTECTED_RETRIEVAL_READ,
                "resource.knowledge.operational-protected-retrieval",
                operational_knowledge_protected_retrieval_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
        )
        for request in requests:
            if not (await self._service.evaluate(request)).allowed:
                raise ProtectedModelContextError("protected_model_context_permission_denied")

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
