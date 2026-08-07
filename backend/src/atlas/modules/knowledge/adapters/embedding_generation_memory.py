from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.embedding_generation import (
    OperationalKnowledgeEmbeddingClaim,
    OperationalKnowledgeEmbeddingPolicySnapshot,
    OperationalKnowledgeEmbeddingRecord,
)


class InMemoryOperationalKnowledgeEmbeddingPolicySource:
    def __init__(self, policies: tuple[OperationalKnowledgeEmbeddingPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeEmbeddingPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeEmbeddingRepository:
    def __init__(self) -> None:
        self._claims: dict[str, OperationalKnowledgeEmbeddingClaim] = {}
        self._claim_chunks: dict[str, str] = {}
        self._claim_idempotency: dict[tuple[str, str], str] = {}
        self._records: dict[str, OperationalKnowledgeEmbeddingRecord] = {}
        self._record_chunks: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, embedding_set_id: str) -> OperationalKnowledgeEmbeddingRecord | None:
        return self._records.get(embedding_set_id)

    async def get_claim_by_chunk_set(
        self, *, chunk_set_id: str
    ) -> OperationalKnowledgeEmbeddingClaim | None:
        claim_id = self._claim_chunks.get(chunk_set_id)
        return self._claims.get(claim_id) if claim_id else None

    async def claim(self, claim: OperationalKnowledgeEmbeddingClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        async with self._lock:
            if (
                claim.claim_id in self._claims
                or claim.chunk_set_id in self._claim_chunks
                or key in self._claim_idempotency
            ):
                return False
            self._claims[claim.claim_id] = claim
            self._claim_chunks[claim.chunk_set_id] = claim.claim_id
            self._claim_idempotency[key] = claim.claim_id
            return True

    async def add(self, record: OperationalKnowledgeEmbeddingRecord) -> bool:
        async with self._lock:
            if (
                record.embedding_set_id in self._records
                or record.chunk_set_id in self._record_chunks
            ):
                return False
            self._records[record.embedding_set_id] = record
            self._record_chunks[record.chunk_set_id] = record.embedding_set_id
            return True

    async def close(self) -> None:
        return None
