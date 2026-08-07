from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.final_resolution import (
    OperationalKnowledgeFinalResolutionClaim,
    OperationalKnowledgeFinalResolutionPolicySnapshot,
    OperationalKnowledgeFinalResolutionRecord,
)


class InMemoryOperationalKnowledgeFinalResolutionPolicySource:
    def __init__(
        self, policies: tuple[OperationalKnowledgeFinalResolutionPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeFinalResolutionPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeFinalResolutionRepository:
    def __init__(self) -> None:
        self._claims: dict[str, OperationalKnowledgeFinalResolutionClaim] = {}
        self._claim_requests: dict[str, str] = {}
        self._claim_idempotency: dict[tuple[str, str], str] = {}
        self._records: dict[str, OperationalKnowledgeFinalResolutionRecord] = {}
        self._record_requests: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, resolution_id: str) -> OperationalKnowledgeFinalResolutionRecord | None:
        return self._records.get(resolution_id)

    async def get_by_review_request(
        self, *, review_request_id: str
    ) -> OperationalKnowledgeFinalResolutionRecord | None:
        resolution_id = self._record_requests.get(review_request_id)
        return self._records.get(resolution_id) if resolution_id else None

    async def get_claim_by_review_request(
        self, *, review_request_id: str
    ) -> OperationalKnowledgeFinalResolutionClaim | None:
        claim_id = self._claim_requests.get(review_request_id)
        return self._claims.get(claim_id) if claim_id else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeFinalResolutionClaim | None:
        claim_id = self._claim_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return self._claims.get(claim_id) if claim_id else None

    async def claim(self, claim: OperationalKnowledgeFinalResolutionClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        async with self._lock:
            if (
                claim.claim_id in self._claims
                or claim.review_request_id in self._claim_requests
                or key in self._claim_idempotency
            ):
                return False
            self._claims[claim.claim_id] = claim
            self._claim_requests[claim.review_request_id] = claim.claim_id
            self._claim_idempotency[key] = claim.claim_id
            return True

    async def add(self, record: OperationalKnowledgeFinalResolutionRecord) -> bool:
        async with self._lock:
            if (
                record.resolution_id in self._records
                or record.review_request_id in self._record_requests
            ):
                return False
            self._records[record.resolution_id] = record
            self._record_requests[record.review_request_id] = record.resolution_id
            return True

    async def close(self) -> None:
        return None
