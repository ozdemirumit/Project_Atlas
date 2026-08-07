from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.index_staging_validation import OperationalKnowledgeIndexRecord
from atlas.modules.knowledge.domain.retrieval_index_publication import (
    OperationalKnowledgeRetrievalPublicationClaim,
    OperationalKnowledgeRetrievalPublicationInstruction,
    OperationalKnowledgeRetrievalPublicationPolicySnapshot,
    OperationalKnowledgeRetrievalPublicationReceipt,
    OperationalKnowledgeRetrievalPublicationRecord,
)


class OperationalKnowledgeRetrievalPublicationError(RuntimeError):
    pass


class OperationalKnowledgeRetrievalPublicationUncertainError(
    OperationalKnowledgeRetrievalPublicationError
):
    pass


class OperationalKnowledgeIndexStagingSource(Protocol):
    async def source_for_retrieval_publication(
        self, *, index_staging_id: str
    ) -> OperationalKnowledgeIndexRecord | None: ...


class OperationalKnowledgeRetrievalPublicationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeRetrievalPublicationPolicySnapshot | None: ...


class OperationalKnowledgeRetrievalPublisher(Protocol):
    async def publish(
        self, instruction: OperationalKnowledgeRetrievalPublicationInstruction
    ) -> OperationalKnowledgeRetrievalPublicationReceipt: ...


class OperationalKnowledgeRetrievalPublicationRepository(Protocol):
    async def get(
        self, *, publication_id: str
    ) -> OperationalKnowledgeRetrievalPublicationRecord | None: ...

    async def get_claim_by_index_staging(
        self, *, index_staging_id: str
    ) -> OperationalKnowledgeRetrievalPublicationClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeRetrievalPublicationClaim) -> bool: ...
    async def add(self, record: OperationalKnowledgeRetrievalPublicationRecord) -> bool: ...
    async def close(self) -> None: ...


class OperationalKnowledgeRetrievalPublicationPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
