from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.ai.application.protected_draft_adjudication_ports import (
    ProtectedDraftAdjudicationError,
)
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_DRAFT_ADJUDICATION_CREATE,
    AI_PROTECTED_DRAFT_ADJUDICATION_READ,
    AI_PROTECTED_MODEL_CONTEXT_READ,
    AI_PROTECTED_MODEL_INVOCATION_READ,
    ai_protected_draft_adjudication_scope,
    ai_protected_model_context_scope,
    ai_protected_model_invocation_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest, ResourceScope
from atlas.modules.identity.domain.models import AuthenticatedSubject


class AuthorizationProtectedDraftAdjudicationPermissionAuthorizer:
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
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_permission_denied")
        now = datetime.now(UTC)
        requests = (
            self._request(
                actor,
                AI_PROTECTED_DRAFT_ADJUDICATION_CREATE,
                "resource.ai.protected-draft-adjudication",
                ai_protected_draft_adjudication_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                AI_PROTECTED_DRAFT_ADJUDICATION_READ,
                "resource.ai.protected-draft-adjudication",
                ai_protected_draft_adjudication_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                AI_PROTECTED_MODEL_INVOCATION_READ,
                "resource.ai.protected-model-invocation",
                ai_protected_model_invocation_scope(
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
        )
        for request in requests:
            if not (await self._service.evaluate(request)).allowed:
                raise ProtectedDraftAdjudicationError(
                    "protected_draft_adjudication_permission_denied"
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
