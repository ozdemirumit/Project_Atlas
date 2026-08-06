from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    KNOWLEDGE_DRAFT_REVIEW_REQUEST_CREATE,
    KNOWLEDGE_EVIDENCE_DRAFT_READ,
    operational_evidence_knowledge_draft_scope,
    operational_knowledge_review_request_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.draft_review_request_ports import (
    OperationalKnowledgeReviewRequestError,
)


class AuthorizationOperationalKnowledgeReviewRequestPermissionAuthorizer:
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
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_permission_denied"
            )
        requests = (
            AuthorizationRequest(
                subject=actor,
                permission_id=KNOWLEDGE_DRAFT_REVIEW_REQUEST_CREATE,
                resource_type="resource.knowledge.operational-review-requests",
                scope=operational_knowledge_review_request_scope(
                    organization_id,
                    self._environment,
                    CapabilityClass.C3_CONTROLLED_CHANGE,
                ),
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
            ),
            AuthorizationRequest(
                subject=actor,
                permission_id=KNOWLEDGE_EVIDENCE_DRAFT_READ,
                resource_type="resource.knowledge.operational-evidence-drafts",
                scope=operational_evidence_knowledge_draft_scope(
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
                raise OperationalKnowledgeReviewRequestError(
                    "operational_knowledge_review_request_permission_denied"
                )
