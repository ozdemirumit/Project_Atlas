from __future__ import annotations

from atlas.modules.ai.application.protected_recommendation_candidate_generation_ports import (
    ProtectedRecommendationCandidatePolicySource,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateClaim,
    ProtectedRecommendationCandidatePolicySnapshot,
    ProtectedRecommendationCandidateRecord,
)


class MemoryProtectedRecommendationCandidateRepository:
    def __init__(self) -> None:
        self._claims: dict[str, ProtectedRecommendationCandidateClaim] = {}
        self._claim_by_idempotency: dict[tuple[str, str], str] = {}
        self._claim_by_presentation: dict[str, str] = {}
        self._records: dict[str, ProtectedRecommendationCandidateRecord] = {}

    async def claim(self, claim: ProtectedRecommendationCandidateClaim) -> bool:
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
    ) -> ProtectedRecommendationCandidateClaim | None:
        claim_id = self._claim_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return None if claim_id is None else self._claims.get(claim_id)

    async def get_claim_by_presentation(
        self, *, presentation_id: str
    ) -> ProtectedRecommendationCandidateClaim | None:
        claim_id = self._claim_by_presentation.get(presentation_id)
        return None if claim_id is None else self._claims.get(claim_id)

    async def save(self, record: ProtectedRecommendationCandidateRecord) -> None:
        if record.candidate_set_id in self._records:
            raise RuntimeError("protected_recommendation_candidate_set_already_exists")
        self._records[record.candidate_set_id] = record

    async def get(self, *, candidate_set_id: str) -> ProtectedRecommendationCandidateRecord | None:
        return self._records.get(candidate_set_id)

    async def close(self) -> None:
        return None


class InMemoryProtectedRecommendationCandidatePolicySource(
    ProtectedRecommendationCandidatePolicySource
):
    def __init__(
        self, policies: tuple[ProtectedRecommendationCandidatePolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedRecommendationCandidatePolicySnapshot | None:
        return self._policies.get(policy_id)
