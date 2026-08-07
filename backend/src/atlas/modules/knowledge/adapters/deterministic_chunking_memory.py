from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.deterministic_chunking import (
    OperationalKnowledgeChunkingClaim,
    OperationalKnowledgeChunkingPolicySnapshot,
    OperationalKnowledgeChunkingRecord,
)


class InMemoryOperationalKnowledgeChunkingPolicySource:
    def __init__(self, policies: tuple[OperationalKnowledgeChunkingPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeChunkingPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeChunkingRepository:
    def __init__(self) -> None:
        self._claims: dict[str, OperationalKnowledgeChunkingClaim] = {}
        self._claim_materializations: dict[str, str] = {}
        self._claim_idempotency: dict[tuple[str, str], str] = {}
        self._records: dict[str, OperationalKnowledgeChunkingRecord] = {}
        self._record_materializations: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, chunk_set_id: str) -> OperationalKnowledgeChunkingRecord | None:
        return self._records.get(chunk_set_id)

    async def get_claim_by_materialization(
        self, *, materialization_id: str
    ) -> OperationalKnowledgeChunkingClaim | None:
        claim_id = self._claim_materializations.get(materialization_id)
        return self._claims.get(claim_id) if claim_id else None

    async def claim(self, claim: OperationalKnowledgeChunkingClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        async with self._lock:
            if (
                claim.claim_id in self._claims
                or claim.materialization_id in self._claim_materializations
                or key in self._claim_idempotency
            ):
                return False
            self._claims[claim.claim_id] = claim
            self._claim_materializations[claim.materialization_id] = claim.claim_id
            self._claim_idempotency[key] = claim.claim_id
            return True

    async def add(self, record: OperationalKnowledgeChunkingRecord) -> bool:
        async with self._lock:
            if (
                record.chunk_set_id in self._records
                or record.materialization_id in self._record_materializations
            ):
                return False
            self._records[record.chunk_set_id] = record
            self._record_materializations[record.materialization_id] = record.chunk_set_id
            return True

    async def close(self) -> None:
        return None
