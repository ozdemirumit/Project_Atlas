from __future__ import annotations

from atlas.modules.recommendations.application.review_request_ports import (
    RecommendationReviewRequestPolicySource,
)
from atlas.modules.recommendations.domain.review_request import (
    RecommendationReviewRequestClaim,
    RecommendationReviewRequestPolicySnapshot,
    RecommendationReviewRequestRecord,
)


class MemoryRecommendationReviewRequestRepository:
    def __init__(self) -> None:
        self._claims: dict[str, RecommendationReviewRequestClaim] = {}
        self._claim_by_idempotency: dict[tuple[str, str], str] = {}
        self._claim_by_assessment: dict[str, str] = {}
        self._records: dict[str, RecommendationReviewRequestRecord] = {}

    async def claim(self, claim: RecommendationReviewRequestClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        if (
            key in self._claim_by_idempotency
            or claim.readiness_assessment_id in self._claim_by_assessment
        ):
            return False
        self._claims[claim.claim_id] = claim
        self._claim_by_idempotency[key] = claim.claim_id
        self._claim_by_assessment[claim.readiness_assessment_id] = claim.claim_id
        return True

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationReviewRequestClaim | None:
        claim_id = self._claim_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return None if claim_id is None else self._claims.get(claim_id)

    async def save(self, record: RecommendationReviewRequestRecord) -> None:
        if record.review_request_id in self._records:
            raise RuntimeError("recommendation_review_request_already_exists")
        self._records[record.review_request_id] = record

    async def get(self, *, review_request_id: str) -> RecommendationReviewRequestRecord | None:
        return self._records.get(review_request_id)

    async def close(self) -> None:
        return None


class InMemoryRecommendationReviewRequestPolicySource(RecommendationReviewRequestPolicySource):
    def __init__(self, policies: tuple[RecommendationReviewRequestPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationReviewRequestPolicySnapshot | None:
        return self._policies.get(policy_id)
