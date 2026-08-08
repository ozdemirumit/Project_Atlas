from __future__ import annotations

from typing import Protocol

from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactReport,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryClaim,
    ProtectedCandidateRiskRecoveryInstruction,
    ProtectedCandidateRiskRecoveryPolicySnapshot,
    ProtectedCandidateRiskRecoveryReceipt,
    ProtectedCandidateRiskRecoveryRecord,
    ProtectedCandidateRiskRecoveryReport,
    ProtectedOperationalEvidenceSnapshot,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateSet,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


class ProtectedCandidateRiskRecoveryError(RuntimeError):
    pass


class ProtectedCandidateRiskRecoveryUncertainError(ProtectedCandidateRiskRecoveryError):
    pass


class ProtectedCandidateRiskRecoveryRepository(Protocol):
    async def claim(self, claim: ProtectedCandidateRiskRecoveryClaim) -> bool: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedCandidateRiskRecoveryClaim | None: ...

    async def get_claim_by_impact_analysis(
        self, *, impact_analysis_id: str
    ) -> ProtectedCandidateRiskRecoveryClaim | None: ...

    async def save(self, record: ProtectedCandidateRiskRecoveryRecord) -> None: ...

    async def get(self, *, completion_id: str) -> ProtectedCandidateRiskRecoveryRecord | None: ...

    async def close(self) -> None: ...


class ProtectedCandidateRiskRecoveryPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedCandidateRiskRecoveryPolicySnapshot | None: ...


class ProtectedOperationalEvidenceSource(Protocol):
    async def get_by_id(
        self, *, snapshot_id: str
    ) -> ProtectedOperationalEvidenceSnapshot | None: ...


class ProtectedCandidateRiskRecoveryPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedProtectedCandidateRiskRecoveryAssessor(Protocol):
    async def complete(
        self,
        instruction: ProtectedCandidateRiskRecoveryInstruction,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        evidence_snapshot: ProtectedOperationalEvidenceSnapshot,
    ) -> tuple[ProtectedCandidateRiskRecoveryReceipt, ProtectedCandidateRiskRecoveryReport]: ...

    async def rehydrate(
        self,
        *,
        record: ProtectedCandidateRiskRecoveryRecord,
        completion_authorization_digest: str,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        evidence_snapshot: ProtectedOperationalEvidenceSnapshot,
    ) -> tuple[ProtectedCandidateRiskRecoveryReceipt, ProtectedCandidateRiskRecoveryReport]: ...
