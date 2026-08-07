from __future__ import annotations

from atlas.modules.ai.application.protected_answer_presentation_ports import (
    ProtectedAnswerPresentationPolicySource,
)
from atlas.modules.ai.domain.protected_answer_presentation import (
    ProtectedAnswerPresentationClaim,
    ProtectedAnswerPresentationPolicySnapshot,
    ProtectedAnswerPresentationRecord,
)


class MemoryProtectedAnswerPresentationRepository:
    def __init__(self) -> None:
        self._claims: dict[str, ProtectedAnswerPresentationClaim] = {}
        self._claim_by_idempotency: dict[tuple[str, str], str] = {}
        self._claim_by_adjudication: dict[str, str] = {}
        self._records: dict[str, ProtectedAnswerPresentationRecord] = {}

    async def claim(self, claim: ProtectedAnswerPresentationClaim) -> bool:
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
    ) -> ProtectedAnswerPresentationClaim | None:
        claim_id = self._claim_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return None if claim_id is None else self._claims.get(claim_id)

    async def get_claim_by_adjudication(
        self, *, adjudication_id: str
    ) -> ProtectedAnswerPresentationClaim | None:
        claim_id = self._claim_by_adjudication.get(adjudication_id)
        return None if claim_id is None else self._claims.get(claim_id)

    async def save(self, record: ProtectedAnswerPresentationRecord) -> None:
        if record.presentation_id in self._records:
            raise RuntimeError("protected_answer_presentation_already_exists")
        self._records[record.presentation_id] = record

    async def get(self, *, presentation_id: str) -> ProtectedAnswerPresentationRecord | None:
        return self._records.get(presentation_id)

    async def close(self) -> None:
        return None


class InMemoryProtectedAnswerPresentationPolicySource(ProtectedAnswerPresentationPolicySource):
    def __init__(self, policies: tuple[ProtectedAnswerPresentationPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedAnswerPresentationPolicySnapshot | None:
        return self._policies.get(policy_id)
