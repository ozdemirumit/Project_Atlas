from __future__ import annotations

from atlas.modules.ai.application.protected_candidate_risk_recovery_completion_ports import (
    ProtectedCandidateRiskRecoveryPolicySource,
    ProtectedOperationalEvidenceSource,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryClaim,
    ProtectedCandidateRiskRecoveryPolicySnapshot,
    ProtectedCandidateRiskRecoveryRecord,
    ProtectedOperationalEvidenceSnapshot,
)


class MemoryProtectedCandidateRiskRecoveryRepository:
    def __init__(self) -> None:
        self._claims: dict[str, ProtectedCandidateRiskRecoveryClaim] = {}
        self._claim_by_idempotency: dict[tuple[str, str], str] = {}
        self._claim_by_impact: dict[str, str] = {}
        self._records: dict[str, ProtectedCandidateRiskRecoveryRecord] = {}

    async def claim(self, claim: ProtectedCandidateRiskRecoveryClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        if key in self._claim_by_idempotency or claim.impact_analysis_id in self._claim_by_impact:
            return False
        self._claims[claim.claim_id] = claim
        self._claim_by_idempotency[key] = claim.claim_id
        self._claim_by_impact[claim.impact_analysis_id] = claim.claim_id
        return True

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedCandidateRiskRecoveryClaim | None:
        claim_id = self._claim_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return None if claim_id is None else self._claims.get(claim_id)

    async def get_claim_by_impact_analysis(
        self, *, impact_analysis_id: str
    ) -> ProtectedCandidateRiskRecoveryClaim | None:
        claim_id = self._claim_by_impact.get(impact_analysis_id)
        return None if claim_id is None else self._claims.get(claim_id)

    async def save(self, record: ProtectedCandidateRiskRecoveryRecord) -> None:
        if record.completion_id in self._records:
            raise RuntimeError("protected_candidate_risk_recovery_already_exists")
        self._records[record.completion_id] = record

    async def get(self, *, completion_id: str) -> ProtectedCandidateRiskRecoveryRecord | None:
        return self._records.get(completion_id)

    async def close(self) -> None:
        return None


class InMemoryProtectedCandidateRiskRecoveryPolicySource(
    ProtectedCandidateRiskRecoveryPolicySource
):
    def __init__(self, policies: tuple[ProtectedCandidateRiskRecoveryPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedCandidateRiskRecoveryPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryProtectedOperationalEvidenceSource(ProtectedOperationalEvidenceSource):
    def __init__(self, snapshots: tuple[ProtectedOperationalEvidenceSnapshot, ...]) -> None:
        self._snapshots = {snapshot.snapshot_id: snapshot for snapshot in snapshots}

    async def get_by_id(self, *, snapshot_id: str) -> ProtectedOperationalEvidenceSnapshot | None:
        return self._snapshots.get(snapshot_id)
