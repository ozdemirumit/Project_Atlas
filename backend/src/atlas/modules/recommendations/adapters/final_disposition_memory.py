from __future__ import annotations

import asyncio

from atlas.modules.recommendations.domain.final_disposition import (
    FinalRecommendationDispositionClaim,
    FinalRecommendationDispositionPolicySnapshot,
    FinalRecommendationDispositionRecord,
)


class InMemoryFinalRecommendationDispositionPolicySource:
    def __init__(self, policies: tuple[FinalRecommendationDispositionPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> FinalRecommendationDispositionPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryFinalRecommendationDispositionRepository:
    def __init__(self) -> None:
        self._claims: dict[str, FinalRecommendationDispositionClaim] = {}
        self._claim_requests: dict[str, str] = {}
        self._claim_idempotency: dict[tuple[str, str], str] = {}
        self._records: dict[str, FinalRecommendationDispositionRecord] = {}
        self._record_requests: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, disposition_id: str) -> FinalRecommendationDispositionRecord | None:
        return self._records.get(disposition_id)

    async def get_by_review_request(
        self, *, review_request_id: str
    ) -> FinalRecommendationDispositionRecord | None:
        disposition_id = self._record_requests.get(review_request_id)
        return self._records.get(disposition_id) if disposition_id else None

    async def get_claim_by_review_request(
        self, *, review_request_id: str
    ) -> FinalRecommendationDispositionClaim | None:
        claim_id = self._claim_requests.get(review_request_id)
        return self._claims.get(claim_id) if claim_id else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> FinalRecommendationDispositionClaim | None:
        claim_id = self._claim_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return self._claims.get(claim_id) if claim_id else None

    async def claim(self, claim: FinalRecommendationDispositionClaim) -> bool:
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

    async def add(self, record: FinalRecommendationDispositionRecord) -> bool:
        async with self._lock:
            if (
                record.disposition_id in self._records
                or record.review_request_id in self._record_requests
            ):
                return False
            self._records[record.disposition_id] = record
            self._record_requests[record.review_request_id] = record.disposition_id
            return True

    async def close(self) -> None:
        return None
