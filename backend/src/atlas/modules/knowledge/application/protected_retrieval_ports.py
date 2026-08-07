from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.protected_retrieval import (
    OperationalKnowledgeEvidencePackage,
    OperationalKnowledgeRetrievalClaim,
    OperationalKnowledgeRetrievalInstruction,
    OperationalKnowledgeRetrievalPolicySnapshot,
    OperationalKnowledgeRetrievalReceipt,
    OperationalKnowledgeRetrievalRecord,
)
from atlas.modules.knowledge.domain.retrieval_index_publication import (
    OperationalKnowledgeRetrievalPublicationRecord,
)


class OperationalKnowledgeRetrievalError(RuntimeError):
    pass


class OperationalKnowledgeRetrievalUncertainError(OperationalKnowledgeRetrievalError):
    pass


class OperationalKnowledgeRetrievalPublicationSource(Protocol):
    async def source_for_governed_retrieval(
        self, *, publication_id: str
    ) -> OperationalKnowledgeRetrievalPublicationRecord | None: ...


class OperationalKnowledgeRetrievalPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeRetrievalPolicySnapshot | None: ...


class OperationalKnowledgeTrustedRetriever(Protocol):
    async def retrieve(
        self, instruction: OperationalKnowledgeRetrievalInstruction
    ) -> tuple[OperationalKnowledgeRetrievalReceipt, OperationalKnowledgeEvidencePackage]: ...

    async def rehydrate(
        self,
        *,
        record: OperationalKnowledgeRetrievalRecord,
        authorization_context_digest: str,
    ) -> OperationalKnowledgeEvidencePackage: ...


class OperationalKnowledgeRetrievalRepository(Protocol):
    async def get(self, *, retrieval_id: str) -> OperationalKnowledgeRetrievalRecord | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeRetrievalClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeRetrievalClaim) -> bool: ...
    async def add(self, record: OperationalKnowledgeRetrievalRecord) -> bool: ...
    async def close(self) -> None: ...


class OperationalKnowledgeRetrievalPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
