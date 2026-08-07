from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.embedding_generation import (
    OperationalKnowledgeEmbeddingRecord,
)
from atlas.modules.knowledge.domain.index_staging_validation import (
    OperationalKnowledgeIndexClaim,
    OperationalKnowledgeIndexInstruction,
    OperationalKnowledgeIndexPolicySnapshot,
    OperationalKnowledgeIndexReceipt,
    OperationalKnowledgeIndexRecord,
)


class OperationalKnowledgeIndexError(RuntimeError):
    pass


class OperationalKnowledgeIndexUncertainError(OperationalKnowledgeIndexError):
    pass


class OperationalKnowledgeEmbeddingSetSource(Protocol):
    async def source_for_index_staging(
        self, *, embedding_set_id: str
    ) -> OperationalKnowledgeEmbeddingRecord | None: ...


class OperationalKnowledgeIndexPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeIndexPolicySnapshot | None: ...


class OperationalKnowledgeIndexer(Protocol):
    async def stage_and_validate(
        self, instruction: OperationalKnowledgeIndexInstruction
    ) -> OperationalKnowledgeIndexReceipt: ...


class OperationalKnowledgeIndexRepository(Protocol):
    async def get(self, *, index_staging_id: str) -> OperationalKnowledgeIndexRecord | None: ...

    async def get_claim_by_embedding_set(
        self, *, embedding_set_id: str
    ) -> OperationalKnowledgeIndexClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeIndexClaim) -> bool: ...
    async def add(self, record: OperationalKnowledgeIndexRecord) -> bool: ...
    async def close(self) -> None: ...


class OperationalKnowledgeIndexPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
