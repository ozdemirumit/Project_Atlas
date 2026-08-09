from __future__ import annotations

from atlas.modules.recommendations.application.promotion_ports import (
    RecommendationPromotionPolicySource,
)
from atlas.modules.recommendations.domain.promotion import (
    PromotedRecommendationArtifact,
    RecommendationPromotionClaim,
    RecommendationPromotionPolicySnapshot,
)


class MemoryRecommendationPromotionRepository:
    def __init__(self) -> None:
        self._claims: dict[str, RecommendationPromotionClaim] = {}
        self._claim_by_idempotency: dict[tuple[str, str], str] = {}
        self._claim_by_presentation: dict[str, str] = {}
        self._artifacts: dict[str, PromotedRecommendationArtifact] = {}

    async def claim(self, claim: RecommendationPromotionClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        if (
            key in self._claim_by_idempotency
            or claim.presentation_id in self._claim_by_presentation
        ):
            return False
        self._claims[claim.claim_id] = claim
        self._claim_by_idempotency[key] = claim.claim_id
        self._claim_by_presentation[claim.presentation_id] = claim.claim_id
        return True

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationPromotionClaim | None:
        claim_id = self._claim_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return None if claim_id is None else self._claims.get(claim_id)

    async def save(self, artifact: PromotedRecommendationArtifact) -> None:
        if artifact.recommendation_id in self._artifacts:
            raise RuntimeError("recommendation_promotion_already_exists")
        self._artifacts[artifact.recommendation_id] = artifact

    async def get(self, *, recommendation_id: str) -> PromotedRecommendationArtifact | None:
        return self._artifacts.get(recommendation_id)

    async def close(self) -> None:
        return None


class InMemoryRecommendationPromotionPolicySource(RecommendationPromotionPolicySource):
    def __init__(self, policies: tuple[RecommendationPromotionPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(self, *, policy_id: str) -> RecommendationPromotionPolicySnapshot | None:
        return self._policies.get(policy_id)
