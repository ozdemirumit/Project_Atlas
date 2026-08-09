from __future__ import annotations

from atlas.modules.ai.application.protected_recommendation_presentation_ports import (
    ProtectedRecommendationPresentationPolicySource,
)
from atlas.modules.ai.domain.protected_recommendation_presentation import (
    ProtectedRecommendationPresentationClaim,
    ProtectedRecommendationPresentationPolicySnapshot,
    ProtectedRecommendationPresentationRecord,
)


class MemoryProtectedRecommendationPresentationRepository:
    def __init__(self) -> None:
        self._claims: dict[str, ProtectedRecommendationPresentationClaim] = {}
        self._claim_by_idempotency: dict[tuple[str, str], str] = {}
        self._claim_by_adjudication: dict[str, str] = {}
        self._records: dict[str, ProtectedRecommendationPresentationRecord] = {}

    async def claim(self, claim: ProtectedRecommendationPresentationClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        if (
            key in self._claim_by_idempotency
            or claim.adjudication_id in self._claim_by_adjudication
        ):
            return False
        self._claims[claim.claim_id] = claim
        self._claim_by_idempotency[key] = claim.claim_id
        self._claim_by_adjudication[claim.adjudication_id] = claim.claim_id
        return True

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedRecommendationPresentationClaim | None:
        claim_id = self._claim_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return None if claim_id is None else self._claims.get(claim_id)

    async def save(self, record: ProtectedRecommendationPresentationRecord) -> None:
        if record.presentation_id in self._records:
            raise RuntimeError("protected_recommendation_presentation_already_exists")
        self._records[record.presentation_id] = record

    async def get(
        self, *, presentation_id: str
    ) -> ProtectedRecommendationPresentationRecord | None:
        return self._records.get(presentation_id)

    async def close(self) -> None:
        return None


class InMemoryProtectedRecommendationPresentationPolicySource(
    ProtectedRecommendationPresentationPolicySource
):
    def __init__(
        self, policies: tuple[ProtectedRecommendationPresentationPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedRecommendationPresentationPolicySnapshot | None:
        return self._policies.get(policy_id)
