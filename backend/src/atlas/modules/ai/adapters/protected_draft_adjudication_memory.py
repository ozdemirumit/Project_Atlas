from __future__ import annotations

import asyncio

from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationClaim,
    ProtectedDraftAdjudicationPolicySnapshot,
    ProtectedDraftAdjudicationRecord,
)


class InMemoryProtectedDraftAdjudicationPolicySource:
    def __init__(self, policies: tuple[ProtectedDraftAdjudicationPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(self, *, policy_id: str) -> ProtectedDraftAdjudicationPolicySnapshot | None:
        return self._policies.get(policy_id)


class MemoryProtectedDraftAdjudicationRepository:
    def __init__(self) -> None:
        self._claims: dict[str, ProtectedDraftAdjudicationClaim] = {}
        self._records: dict[str, ProtectedDraftAdjudicationRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, adjudication_id: str) -> ProtectedDraftAdjudicationRecord | None:
        return self._records.get(adjudication_id)

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedDraftAdjudicationClaim | None:
        return next(
            (
                claim
                for claim in self._claims.values()
                if claim.claimed_by_subject_digest == claimed_by_subject_digest
                and claim.idempotency_digest == idempotency_digest
            ),
            None,
        )

    async def claim(self, claim: ProtectedDraftAdjudicationClaim) -> bool:
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

    async def add(self, record: ProtectedDraftAdjudicationRecord) -> bool:
        async with self._lock:
            if record.adjudication_id in self._records:
                return False
            self._records[record.adjudication_id] = record
            return True

    async def close(self) -> None:
        return None
