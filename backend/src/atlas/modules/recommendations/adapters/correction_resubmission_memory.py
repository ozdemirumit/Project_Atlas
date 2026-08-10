from __future__ import annotations

import asyncio

from atlas.modules.recommendations.domain.correction_resubmission import (
    RecommendationCorrectionClaim,
    RecommendationCorrectionPolicySnapshot,
    RecommendationCorrectionRecord,
)


class InMemoryRecommendationCorrectionPolicySource:
    def __init__(self, policies: tuple[RecommendationCorrectionPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(self, *, policy_id: str) -> RecommendationCorrectionPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryRecommendationCorrectionRepository:
    def __init__(self) -> None:
        self._claims: dict[str, RecommendationCorrectionClaim] = {}
        self._claim_sources: dict[str, str] = {}
        self._claim_idempotency: dict[tuple[str, str], str] = {}
        self._records: dict[str, RecommendationCorrectionRecord] = {}
        self._record_sources: dict[str, str] = {}
        self._record_recommendations: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, correction_id: str) -> RecommendationCorrectionRecord | None:
        return self._records.get(correction_id)

    async def get_by_source_request(
        self, *, source_review_request_id: str
    ) -> RecommendationCorrectionRecord | None:
        correction_id = self._record_sources.get(source_review_request_id)
        return self._records.get(correction_id) if correction_id else None

    async def get_by_new_recommendation(
        self, *, new_recommendation_id: str
    ) -> RecommendationCorrectionRecord | None:
        correction_id = self._record_recommendations.get(new_recommendation_id)
        return self._records.get(correction_id) if correction_id else None

    async def get_claim_by_source_request(
        self, *, source_review_request_id: str
    ) -> RecommendationCorrectionClaim | None:
        claim_id = self._claim_sources.get(source_review_request_id)
        return self._claims.get(claim_id) if claim_id else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationCorrectionClaim | None:
        claim_id = self._claim_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return self._claims.get(claim_id) if claim_id else None

    async def claim(self, claim: RecommendationCorrectionClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        async with self._lock:
            if (
                claim.claim_id in self._claims
                or claim.source_review_request_id in self._claim_sources
                or key in self._claim_idempotency
            ):
                return False
            self._claims[claim.claim_id] = claim
            self._claim_sources[claim.source_review_request_id] = claim.claim_id
            self._claim_idempotency[key] = claim.claim_id
            return True

    async def add(self, record: RecommendationCorrectionRecord) -> bool:
        async with self._lock:
            if (
                record.correction_id in self._records
                or record.source_review_request_id in self._record_sources
                or record.new_recommendation_id in self._record_recommendations
            ):
                return False
            self._records[record.correction_id] = record
            self._record_sources[record.source_review_request_id] = record.correction_id
            self._record_recommendations[record.new_recommendation_id] = record.correction_id
            return True

    async def close(self) -> None:
        return None
