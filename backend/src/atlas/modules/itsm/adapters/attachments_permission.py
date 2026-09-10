from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.authorization.application.bootstrap import (
    ITSM_ATTACHMENT_ELEVATED_READ,
    itsm_attachment_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.itsm.application.attachments import ItsmAttachmentError


class AuthorizationItsmAttachmentPermissionAuthorizer:
    """Mirrors `AuthorizationDocumentKnowledgePermissionAuthorizer` exactly (see
    `knowledge/adapters/document_knowledge_permission.py`, pass 29's precedent): one reusable
    authorizer across every attachment operation, plus a `classification_ceiling()` gated behind
    its own elevated-read permission rather than the calling operation's own permission -- used
    only at download time, mirroring `document_retrieval.py`'s read-time-only use of the same
    pattern.
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
            raise ItsmAttachmentError("itsm_attachment_permission_denied")
        capability_class = (
            CapabilityClass.C1_READ_ONLY
            if permission_id.endswith(".read")
            else CapabilityClass.C2_DIAGNOSTIC
        )
        request = AuthorizationRequest(
            subject=actor,
            permission_id=permission_id,
            resource_type="resource.itsm.attachments",
            scope=itsm_attachment_scope(organization_id, self._environment, capability_class),
            correlation_id=correlation_id,
            requested_at=datetime.now(UTC),
        )
        decision = await self._service.evaluate(request)
        if not decision.allowed:
            raise ItsmAttachmentError("itsm_attachment_permission_denied")

    async def classification_ceiling(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> DataClassification:
        if environment_id != f"environment.{self._environment}":
            raise ItsmAttachmentError("itsm_attachment_permission_denied")
        request = AuthorizationRequest(
            subject=actor,
            permission_id=ITSM_ATTACHMENT_ELEVATED_READ,
            resource_type="resource.itsm.attachments",
            scope=itsm_attachment_scope(
                organization_id, self._environment, CapabilityClass.C1_READ_ONLY
            ),
            correlation_id=correlation_id,
            requested_at=datetime.now(UTC),
        )
        decision = await self._service.evaluate(request)
        if decision.allowed:
            return DataClassification.RESTRICTED
        return DataClassification.INTERNAL
