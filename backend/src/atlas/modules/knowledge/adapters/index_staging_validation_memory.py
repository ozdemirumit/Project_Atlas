from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.index_staging_validation import (
    OperationalKnowledgeIndexClaim,
    OperationalKnowledgeIndexPolicySnapshot,
    OperationalKnowledgeIndexRecord,
)


class InMemoryOperationalKnowledgeIndexPolicySource:
    def __init__(self, policies: tuple[OperationalKnowledgeIndexPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(self, *, policy_id: str) -> OperationalKnowledgeIndexPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeIndexRepository:
    def __init__(self) -> None:
        self._claims: dict[str, OperationalKnowledgeIndexClaim] = {}
        self._claim_embeddings: dict[str, str] = {}
        self._claim_idempotency: dict[tuple[str, str], str] = {}
        self._records: dict[str, OperationalKnowledgeIndexRecord] = {}
        self._record_embeddings: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, index_staging_id: str) -> OperationalKnowledgeIndexRecord | None:
        return self._records.get(index_staging_id)

    async def get_claim_by_embedding_set(
        self, *, embedding_set_id: str
    ) -> OperationalKnowledgeIndexClaim | None:
        claim_id = self._claim_embeddings.get(embedding_set_id)
        return self._claims.get(claim_id) if claim_id else None

    async def claim(self, claim: OperationalKnowledgeIndexClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        async with self._lock:
            if (
                claim.claim_id in self._claims
                or claim.embedding_set_id in self._claim_embeddings
                or key in self._claim_idempotency
            ):
                return False
            self._claims[claim.claim_id] = claim
            self._claim_embeddings[claim.embedding_set_id] = claim.claim_id
            self._claim_idempotency[key] = claim.claim_id
            return True

    async def add(self, record: OperationalKnowledgeIndexRecord) -> bool:
        async with self._lock:
            if (
                record.index_staging_id in self._records
                or record.embedding_set_id in self._record_embeddings
            ):
                return False
            self._records[record.index_staging_id] = record
            self._record_embeddings[record.embedding_set_id] = record.index_staging_id
            return True

    async def close(self) -> None:
        return None
