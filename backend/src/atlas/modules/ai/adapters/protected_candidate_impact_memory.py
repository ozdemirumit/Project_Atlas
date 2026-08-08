from __future__ import annotations

from atlas.modules.ai.application.protected_candidate_impact_enrichment_ports import (
    ProtectedCandidateImpactPolicySource,
)
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactClaim,
    ProtectedCandidateImpactPolicySnapshot,
    ProtectedCandidateImpactRecord,
)


class MemoryProtectedCandidateImpactRepository:
    def __init__(self) -> None:
        self._claims: dict[str, ProtectedCandidateImpactClaim] = {}
        self._claim_by_idempotency: dict[tuple[str, str], str] = {}
        self._claim_by_candidate_set: dict[str, str] = {}
        self._records: dict[str, ProtectedCandidateImpactRecord] = {}

    async def claim(self, claim: ProtectedCandidateImpactClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        if (
            key in self._claim_by_idempotency
            or claim.candidate_set_id in self._claim_by_candidate_set
        ):
            return False
        self._claims[claim.claim_id] = claim
        self._claim_by_idempotency[key] = claim.claim_id
        self._claim_by_candidate_set[claim.candidate_set_id] = claim.claim_id
        return True

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedCandidateImpactClaim | None:
        claim_id = self._claim_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return None if claim_id is None else self._claims.get(claim_id)

    async def get_claim_by_candidate_set(
        self, *, candidate_set_id: str
    ) -> ProtectedCandidateImpactClaim | None:
        claim_id = self._claim_by_candidate_set.get(candidate_set_id)
        return None if claim_id is None else self._claims.get(claim_id)

    async def save(self, record: ProtectedCandidateImpactRecord) -> None:
        if record.impact_analysis_id in self._records:
            raise RuntimeError("protected_candidate_impact_analysis_already_exists")
        self._records[record.impact_analysis_id] = record

    async def get(self, *, impact_analysis_id: str) -> ProtectedCandidateImpactRecord | None:
        return self._records.get(impact_analysis_id)

    async def close(self) -> None:
        return None


class InMemoryProtectedCandidateImpactPolicySource(ProtectedCandidateImpactPolicySource):
    def __init__(self, policies: tuple[ProtectedCandidateImpactPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(self, *, policy_id: str) -> ProtectedCandidateImpactPolicySnapshot | None:
        return self._policies.get(policy_id)
