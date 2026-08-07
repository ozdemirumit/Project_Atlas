from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.model_context_assembly import (
    ProtectedModelContextClaim,
    ProtectedModelContextPolicySnapshot,
    ProtectedModelContextRecord,
)


class InMemoryProtectedModelContextPolicySource:
    def __init__(self, policies: tuple[ProtectedModelContextPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(self, *, policy_id: str) -> ProtectedModelContextPolicySnapshot | None:
        return self._policies.get(policy_id)


class MemoryProtectedModelContextRepository:
    def __init__(self) -> None:
        self._claims: dict[str, ProtectedModelContextClaim] = {}
        self._records: dict[str, ProtectedModelContextRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, context_id: str) -> ProtectedModelContextRecord | None:
        return self._records.get(context_id)

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedModelContextClaim | None:
        return next(
            (
                claim
                for claim in self._claims.values()
                if claim.claimed_by_subject_digest == claimed_by_subject_digest
                and claim.idempotency_digest == idempotency_digest
            ),
            None,
        )

    async def claim(self, claim: ProtectedModelContextClaim) -> bool:
        async with self._lock:
            existing = await self.get_claim_by_idempotency(
                claimed_by_subject_digest=claim.claimed_by_subject_digest,
                idempotency_digest=claim.idempotency_digest,
            )
            if existing is not None or claim.claim_id in self._claims:
                return False
            self._claims[claim.claim_id] = claim
            return True

    async def add(self, record: ProtectedModelContextRecord) -> bool:
        async with self._lock:
            if record.context_id in self._records:
                return False
            self._records[record.context_id] = record
            return True

    async def close(self) -> None:
        return None
