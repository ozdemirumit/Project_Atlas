from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    OPERATION_RESOURCE_CROSS_SUBJECT_ACCESS,
    operation_resource_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.operations.application.ports import OperationResourceError


class AuthorizationOperationResourcePermissionAuthorizer:
    """Mirrors `AuthorizationItsmAttachmentPermissionAuthorizer` /
    `AuthorizationDocumentKnowledgePermissionAuthorizer` exactly: one reusable `authorize()`
    across every operation-resource operation, plus a `cross_subject_access_allowed()` gated
    behind its own elevated permission -- evaluated only when the acting subject does not own the
    operation resource it is trying to read or cancel.
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
            raise OperationResourceError("operation_resource_permission_denied")
        capability_class = (
            CapabilityClass.C1_READ_ONLY
            if permission_id.endswith(".read")
            else CapabilityClass.C2_DIAGNOSTIC
        )
        request = AuthorizationRequest(
            subject=actor,
            permission_id=permission_id,
            resource_type="resource.operations.resources",
            scope=operation_resource_scope(organization_id, self._environment, capability_class),
            correlation_id=correlation_id,
            requested_at=datetime.now(UTC),
        )
        decision = await self._service.evaluate(request)
        if not decision.allowed:
            raise OperationResourceError("operation_resource_permission_denied")

    async def cross_subject_access_allowed(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> bool:
        if environment_id != f"environment.{self._environment}":
            return False
        request = AuthorizationRequest(
            subject=actor,
            permission_id=OPERATION_RESOURCE_CROSS_SUBJECT_ACCESS,
            resource_type="resource.operations.resources",
            scope=operation_resource_scope(
                organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
            ),
            correlation_id=correlation_id,
            requested_at=datetime.now(UTC),
        )
        decision = await self._service.evaluate(request)
        return decision.allowed
