from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    KNOWLEDGE_INDEX_STAGING_READ,
    KNOWLEDGE_RETRIEVAL_PUBLICATION_CREATE,
    KNOWLEDGE_RETRIEVAL_PUBLICATION_READ,
    operational_knowledge_index_staging_scope,
    operational_knowledge_retrieval_publication_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationRequest, ResourceScope
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.retrieval_index_publication_ports import (
    OperationalKnowledgeRetrievalPublicationError,
)


class AuthorizationOperationalKnowledgeRetrievalPublicationPermissionAuthorizer:
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
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_permission_denied"
            )
        now = datetime.now(UTC)
        requests = (
            self._request(
                actor,
                KNOWLEDGE_RETRIEVAL_PUBLICATION_CREATE,
                "resource.knowledge.operational-retrieval-publication",
                operational_knowledge_retrieval_publication_scope(
                    organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_RETRIEVAL_PUBLICATION_READ,
                "resource.knowledge.operational-retrieval-publication",
                operational_knowledge_retrieval_publication_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
            self._request(
                actor,
                KNOWLEDGE_INDEX_STAGING_READ,
                "resource.knowledge.operational-index-staging",
                operational_knowledge_index_staging_scope(
                    organization_id, self._environment, CapabilityClass.C1_READ_ONLY
                ),
                correlation_id,
                now,
            ),
        )
        for request in requests:
            if not (await self._service.evaluate(request)).allowed:
                raise OperationalKnowledgeRetrievalPublicationError(
                    "operational_knowledge_retrieval_publication_permission_denied"
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
