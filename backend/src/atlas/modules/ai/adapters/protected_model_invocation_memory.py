from __future__ import annotations

import asyncio

from atlas.modules.ai.domain.protected_model_invocation import (
    ProtectedModelInvocationClaim,
    ProtectedModelInvocationPolicySnapshot,
    ProtectedModelInvocationRecord,
)


class InMemoryProtectedModelInvocationPolicySource:
    def __init__(self, policies: tuple[ProtectedModelInvocationPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(self, *, policy_id: str) -> ProtectedModelInvocationPolicySnapshot | None:
        return self._policies.get(policy_id)


class MemoryProtectedModelInvocationRepository:
    def __init__(self) -> None:
        self._claims: dict[str, ProtectedModelInvocationClaim] = {}
        self._records: dict[str, ProtectedModelInvocationRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, invocation_id: str) -> ProtectedModelInvocationRecord | None:
        return self._records.get(invocation_id)

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedModelInvocationClaim | None:
        return next(
            (
                claim
                for claim in self._claims.values()
                if claim.claimed_by_subject_digest == claimed_by_subject_digest
                and claim.idempotency_digest == idempotency_digest
            ),
            None,
        )

    async def claim(self, claim: ProtectedModelInvocationClaim) -> bool:
        async with self._lock:
            if (
                await self.get_claim_by_idempotency(
                    claimed_by_subject_digest=claim.claimed_by_subject_digest,
                    idempotency_digest=claim.idempotency_digest,
                )
                or claim.claim_id in self._claims
            ):
                return False
            self._claims[claim.claim_id] = claim
            return True

    async def add(self, record: ProtectedModelInvocationRecord) -> bool:
        async with self._lock:
            if record.invocation_id in self._records:
                return False
            self._records[record.invocation_id] = record
            return True

    async def close(self) -> None:
        return None
