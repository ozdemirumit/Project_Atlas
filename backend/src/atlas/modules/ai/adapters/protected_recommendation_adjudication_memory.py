from __future__ import annotations

from atlas.modules.ai.application.protected_recommendation_adjudication_ports import (
    ProtectedRecommendationAdjudicationPolicySource,
)
from atlas.modules.ai.domain.protected_recommendation_adjudication import (
    ProtectedRecommendationAdjudicationClaim,
    ProtectedRecommendationAdjudicationPolicySnapshot,
    ProtectedRecommendationAdjudicationRecord,
)


class MemoryProtectedRecommendationAdjudicationRepository:
    def __init__(self) -> None:
        self._claims: dict[str, ProtectedRecommendationAdjudicationClaim] = {}
        self._claim_by_idempotency: dict[tuple[str, str], str] = {}
        self._claim_by_completion: dict[str, str] = {}
        self._records: dict[str, ProtectedRecommendationAdjudicationRecord] = {}

    async def claim(self, claim: ProtectedRecommendationAdjudicationClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        if key in self._claim_by_idempotency or claim.completion_id in self._claim_by_completion:
            return False
        self._claims[claim.claim_id] = claim
        self._claim_by_idempotency[key] = claim.claim_id
        self._claim_by_completion[claim.completion_id] = claim.claim_id
        return True

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedRecommendationAdjudicationClaim | None:
        claim_id = self._claim_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return None if claim_id is None else self._claims.get(claim_id)

    async def save(self, record: ProtectedRecommendationAdjudicationRecord) -> None:
        if record.adjudication_id in self._records:
            raise RuntimeError("protected_recommendation_adjudication_already_exists")
        self._records[record.adjudication_id] = record

    async def get(
        self, *, adjudication_id: str
    ) -> ProtectedRecommendationAdjudicationRecord | None:
        return self._records.get(adjudication_id)

    async def close(self) -> None:
        return None


class InMemoryProtectedRecommendationAdjudicationPolicySource(
    ProtectedRecommendationAdjudicationPolicySource
):
    def __init__(
        self, policies: tuple[ProtectedRecommendationAdjudicationPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedRecommendationAdjudicationPolicySnapshot | None:
        return self._policies.get(policy_id)
