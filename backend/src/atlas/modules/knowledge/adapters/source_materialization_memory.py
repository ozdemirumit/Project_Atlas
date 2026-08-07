from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.source_materialization import (
    OperationalKnowledgeSourceMaterializationClaim,
    OperationalKnowledgeSourceMaterializationPolicySnapshot,
    OperationalKnowledgeSourceMaterializationRecord,
)


class InMemoryOperationalKnowledgeSourceMaterializationPolicySource:
    def __init__(
        self, policies: tuple[OperationalKnowledgeSourceMaterializationPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeSourceMaterializationPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeSourceMaterializationRepository:
    def __init__(self) -> None:
        self._claims: dict[str, OperationalKnowledgeSourceMaterializationClaim] = {}
        self._claim_preparations: dict[str, str] = {}
        self._claim_idempotency: dict[tuple[str, str], str] = {}
        self._records: dict[str, OperationalKnowledgeSourceMaterializationRecord] = {}
        self._record_preparations: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, materialization_id: str
    ) -> OperationalKnowledgeSourceMaterializationRecord | None:
        return self._records.get(materialization_id)

    async def get_claim_by_preparation(
        self, *, preparation_id: str
    ) -> OperationalKnowledgeSourceMaterializationClaim | None:
        claim_id = self._claim_preparations.get(preparation_id)
        return self._claims.get(claim_id) if claim_id else None

    async def claim(self, claim: OperationalKnowledgeSourceMaterializationClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        async with self._lock:
            if (
                claim.claim_id in self._claims
                or claim.preparation_id in self._claim_preparations
                or key in self._claim_idempotency
            ):
                return False
            self._claims[claim.claim_id] = claim
            self._claim_preparations[claim.preparation_id] = claim.claim_id
            self._claim_idempotency[key] = claim.claim_id
            return True

    async def add(self, record: OperationalKnowledgeSourceMaterializationRecord) -> bool:
        async with self._lock:
            if (
                record.materialization_id in self._records
                or record.preparation_id in self._record_preparations
            ):
                return False
            self._records[record.materialization_id] = record
            self._record_preparations[record.preparation_id] = record.materialization_id
            return True

    async def close(self) -> None:
        return None
