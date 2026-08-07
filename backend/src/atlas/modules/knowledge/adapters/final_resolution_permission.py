from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    KNOWLEDGE_DRAFT_REVIEW_REQUEST_READ,
    KNOWLEDGE_EVIDENCE_DRAFT_READ,
    KNOWLEDGE_FINAL_RESOLUTION_CREATE,
    KNOWLEDGE_FINAL_RESOLUTION_READ,
    KNOWLEDGE_TRACK_REVIEW_DECISION_READ,
    operational_evidence_knowledge_draft_scope,
    operational_knowledge_final_resolution_scope,
    operational_knowledge_review_request_scope,
    operational_knowledge_track_review_decision_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest, ResourceScope
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.final_resolution_ports import (
    OperationalKnowledgeFinalResolutionError,
)


class AuthorizationOperationalKnowledgeFinalResolutionPermissionAuthorizer:
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
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_permission_denied"
            )
        now = datetime.now(UTC)
        requests = (
            self._request(
                actor,
                KNOWLEDGE_FINAL_RESOLUTION_CREATE,
                "resource.knowledge.operational-final-resolutions",
                operational_knowledge_final_resolution_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_FINAL_RESOLUTION_READ,
                "resource.knowledge.operational-final-resolutions",
                operational_knowledge_final_resolution_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_TRACK_REVIEW_DECISION_READ,
                "resource.knowledge.operational-track-review-decisions",
                operational_knowledge_track_review_decision_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_DRAFT_REVIEW_REQUEST_READ,
                "resource.knowledge.operational-review-requests",
                operational_knowledge_review_request_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_EVIDENCE_DRAFT_READ,
                "resource.knowledge.operational-evidence-drafts",
                operational_evidence_knowledge_draft_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
        )
        for request in requests:
            if not (await self._service.evaluate(request)).allowed:
                raise OperationalKnowledgeFinalResolutionError(
                    "operational_knowledge_final_resolution_permission_denied"
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
