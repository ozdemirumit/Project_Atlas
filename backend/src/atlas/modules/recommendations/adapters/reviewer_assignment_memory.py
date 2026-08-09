from __future__ import annotations

from atlas.modules.recommendations.application.reviewer_assignment_ports import (
    RecommendationReviewerAssignmentPolicySource,
)
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentClaim,
    RecommendationReviewerAssignmentPolicySnapshot,
    RecommendationReviewerAssignmentRecord,
)


class MemoryRecommendationReviewerAssignmentRepository:
    def __init__(self) -> None:
        self._claims: dict[str, RecommendationReviewerAssignmentClaim] = {}
        self._claim_by_idempotency: dict[tuple[str, str], str] = {}
        self._claim_by_request: dict[str, str] = {}
        self._records: dict[str, RecommendationReviewerAssignmentRecord] = {}

    async def claim(self, claim: RecommendationReviewerAssignmentClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        if key in self._claim_by_idempotency or claim.review_request_id in self._claim_by_request:
            return False
        self._claims[claim.claim_id] = claim
        self._claim_by_idempotency[key] = claim.claim_id
        self._claim_by_request[claim.review_request_id] = claim.claim_id
        return True

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationReviewerAssignmentClaim | None:
        claim_id = self._claim_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return None if claim_id is None else self._claims.get(claim_id)

    async def save(self, record: RecommendationReviewerAssignmentRecord) -> None:
        if record.assignment_set_id in self._records:
            raise RuntimeError("recommendation_reviewer_assignment_already_exists")
        self._records[record.assignment_set_id] = record

    async def get(self, *, assignment_set_id: str) -> RecommendationReviewerAssignmentRecord | None:
        return self._records.get(assignment_set_id)

    async def close(self) -> None:
        return None


class InMemoryRecommendationReviewerAssignmentPolicySource(
    RecommendationReviewerAssignmentPolicySource
):
    def __init__(
        self, policies: tuple[RecommendationReviewerAssignmentPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationReviewerAssignmentPolicySnapshot | None:
        return self._policies.get(policy_id)
