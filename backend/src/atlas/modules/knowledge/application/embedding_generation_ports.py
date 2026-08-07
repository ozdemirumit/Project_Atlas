from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.deterministic_chunking import (
    OperationalKnowledgeChunkingRecord,
)
from atlas.modules.knowledge.domain.embedding_generation import (
    OperationalKnowledgeEmbeddingClaim,
    OperationalKnowledgeEmbeddingInstruction,
    OperationalKnowledgeEmbeddingPolicySnapshot,
    OperationalKnowledgeEmbeddingReceipt,
    OperationalKnowledgeEmbeddingRecord,
)


class OperationalKnowledgeEmbeddingError(RuntimeError):
    pass


class OperationalKnowledgeEmbeddingUncertainError(OperationalKnowledgeEmbeddingError):
    pass


class OperationalKnowledgeChunkSetSource(Protocol):
    async def source_for_embedding(
        self, *, chunk_set_id: str
    ) -> OperationalKnowledgeChunkingRecord | None: ...


class OperationalKnowledgeEmbeddingPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeEmbeddingPolicySnapshot | None: ...


class OperationalKnowledgeEmbedder(Protocol):
    async def embed(
        self, instruction: OperationalKnowledgeEmbeddingInstruction
    ) -> OperationalKnowledgeEmbeddingReceipt: ...


class OperationalKnowledgeEmbeddingRepository(Protocol):
    async def get(self, *, embedding_set_id: str) -> OperationalKnowledgeEmbeddingRecord | None: ...

    async def get_claim_by_chunk_set(
        self, *, chunk_set_id: str
    ) -> OperationalKnowledgeEmbeddingClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeEmbeddingClaim) -> bool: ...
    async def add(self, record: OperationalKnowledgeEmbeddingRecord) -> bool: ...
    async def close(self) -> None: ...


class OperationalKnowledgeEmbeddingPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
