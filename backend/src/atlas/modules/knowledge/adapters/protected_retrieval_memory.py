from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.protected_retrieval import (
    OperationalKnowledgeRetrievalClaim,
    OperationalKnowledgeRetrievalPolicySnapshot,
    OperationalKnowledgeRetrievalRecord,
)


class InMemoryOperationalKnowledgeRetrievalPolicySource:
    def __init__(self, policies: tuple[OperationalKnowledgeRetrievalPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeRetrievalPolicySnapshot | None:
        return self._policies.get(policy_id)


class MemoryOperationalKnowledgeRetrievalRepository:
    def __init__(self) -> None:
        self._claims: dict[str, OperationalKnowledgeRetrievalClaim] = {}
        self._records: dict[str, OperationalKnowledgeRetrievalRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, retrieval_id: str) -> OperationalKnowledgeRetrievalRecord | None:
        return self._records.get(retrieval_id)

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeRetrievalClaim | None:
        return next(
            (
                claim
                for claim in self._claims.values()
                if claim.claimed_by_subject_digest == claimed_by_subject_digest
                and claim.idempotency_digest == idempotency_digest
            ),
            None,
        )

    async def claim(self, claim: OperationalKnowledgeRetrievalClaim) -> bool:
        async with self._lock:
            existing = await self.get_claim_by_idempotency(
                claimed_by_subject_digest=claim.claimed_by_subject_digest,
                idempotency_digest=claim.idempotency_digest,
            )
            if existing is not None or claim.claim_id in self._claims:
                return False
            self._claims[claim.claim_id] = claim
            return True

    async def add(self, record: OperationalKnowledgeRetrievalRecord) -> bool:
        async with self._lock:
            if record.retrieval_id in self._records:
                return False
            self._records[record.retrieval_id] = record
            return True

    async def close(self) -> None:
        return None
