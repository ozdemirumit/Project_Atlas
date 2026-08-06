from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    connector_capability_invocation_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest
from atlas.modules.connectors.application.invocation_authorization_ports import (
    ConnectorInvocationAuthorizationError,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


class AuthorizationConnectorCapabilityPermissionAuthorizer:
    def __init__(self, *, service: AuthorizationService, environment: str) -> None:
        self._service = service
        self._environment = environment

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        permission_id: str,
        capability_id: str,
        capability_class: str,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None:
        if environment_id != f"environment.{self._environment}":
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_capability_permission_denied"
            )
        decision = await self._service.evaluate(
            AuthorizationRequest(
                subject=actor,
                permission_id=permission_id,
                resource_type="resource.connector.capability-invocation",
                scope=connector_capability_invocation_scope(
                    organization_id,
                    self._environment,
                    CapabilityClass(capability_class),
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
                target_metadata=(("capability_id", capability_id),),
            )
        )
        if not decision.allowed:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_capability_permission_denied"
            )
