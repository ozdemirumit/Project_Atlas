from __future__ import annotations

from atlas.modules.recommendations.application.readiness_ports import (
    RecommendationReadinessPolicySource,
)
from atlas.modules.recommendations.domain.readiness import (
    RecommendationReadinessAssessment,
    RecommendationReadinessClaim,
    RecommendationReadinessPolicySnapshot,
)


class MemoryRecommendationReadinessRepository:
    def __init__(self) -> None:
        self._claims: dict[str, RecommendationReadinessClaim] = {}
        self._claim_by_idempotency: dict[tuple[str, str], str] = {}
        self._claim_by_recommendation: dict[str, str] = {}
        self._assessments: dict[str, RecommendationReadinessAssessment] = {}

    async def claim(self, claim: RecommendationReadinessClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        if (
            key in self._claim_by_idempotency
            or claim.recommendation_id in self._claim_by_recommendation
        ):
            return False
        self._claims[claim.claim_id] = claim
        self._claim_by_idempotency[key] = claim.claim_id
        self._claim_by_recommendation[claim.recommendation_id] = claim.claim_id
        return True

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationReadinessClaim | None:
        claim_id = self._claim_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return None if claim_id is None else self._claims.get(claim_id)

    async def save(self, assessment: RecommendationReadinessAssessment) -> None:
        if assessment.assessment_id in self._assessments:
            raise RuntimeError("recommendation_readiness_already_exists")
        self._assessments[assessment.assessment_id] = assessment

    async def get(self, *, assessment_id: str) -> RecommendationReadinessAssessment | None:
        return self._assessments.get(assessment_id)

    async def close(self) -> None:
        return None


class InMemoryRecommendationReadinessPolicySource(RecommendationReadinessPolicySource):
    def __init__(self, policies: tuple[RecommendationReadinessPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(self, *, policy_id: str) -> RecommendationReadinessPolicySnapshot | None:
        return self._policies.get(policy_id)
