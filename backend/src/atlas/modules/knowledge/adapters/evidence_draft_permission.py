from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    CONNECTOR_INVOCATION_EVIDENCE_READ,
    KNOWLEDGE_EVIDENCE_DRAFT_CREATE,
    connector_invocation_evidence_scope,
    operational_evidence_knowledge_draft_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.evidence_draft_ports import (
    OperationalEvidenceKnowledgeDraftError,
)


class AuthorizationOperationalEvidenceKnowledgeDraftPermissionAuthorizer:
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
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_permission_denied"
            )
        requests = (
            AuthorizationRequest(
                subject=actor,
                permission_id=KNOWLEDGE_EVIDENCE_DRAFT_CREATE,
                resource_type="resource.knowledge.operational-evidence-drafts",
                scope=operational_evidence_knowledge_draft_scope(
                    organization_id,
                    self._environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=CONNECTOR_INVOCATION_EVIDENCE_READ,
                resource_type="resource.connector.invocation-evidence",
                scope=connector_invocation_evidence_scope(
                    organization_id,
                    self._environment,
                    CapabilityClass.C1_READ_ONLY,
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            ),
        )
        for request in requests:
            decision = await self._service.evaluate(request)
            if not decision.allowed:
                raise OperationalEvidenceKnowledgeDraftError(
                    "operational_evidence_knowledge_draft_permission_denied"
                )
