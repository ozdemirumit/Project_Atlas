from __future__ import annotations

from typing import Protocol

from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactReport,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryReport,
    ProtectedOperationalEvidenceSnapshot,
)
from atlas.modules.ai.domain.protected_recommendation_adjudication import (
    ProtectedRecommendationAdjudicationClaim,
    ProtectedRecommendationAdjudicationInstruction,
    ProtectedRecommendationAdjudicationPolicySnapshot,
    ProtectedRecommendationAdjudicationReceipt,
    ProtectedRecommendationAdjudicationRecord,
    ProtectedRecommendationAdjudicationReport,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateSet,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


class ProtectedRecommendationAdjudicationError(RuntimeError):
    pass


class ProtectedRecommendationAdjudicationUncertainError(ProtectedRecommendationAdjudicationError):
    pass


class ProtectedRecommendationAdjudicationRepository(Protocol):
    async def claim(self, claim: ProtectedRecommendationAdjudicationClaim) -> bool: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedRecommendationAdjudicationClaim | None: ...

    async def save(self, record: ProtectedRecommendationAdjudicationRecord) -> None: ...

    async def get(
        self, *, adjudication_id: str
    ) -> ProtectedRecommendationAdjudicationRecord | None: ...

    async def close(self) -> None: ...


class ProtectedRecommendationAdjudicationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedRecommendationAdjudicationPolicySnapshot | None: ...


class ProtectedRecommendationAdjudicationPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedProtectedRecommendationAdjudicator(Protocol):
    async def adjudicate(
        self,
        instruction: ProtectedRecommendationAdjudicationInstruction,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        completion_report: ProtectedCandidateRiskRecoveryReport,
        evidence_snapshot: ProtectedOperationalEvidenceSnapshot,
    ) -> tuple[
        ProtectedRecommendationAdjudicationReceipt,
        ProtectedRecommendationAdjudicationReport,
    ]: ...

    async def rehydrate(
        self,
        *,
        record: ProtectedRecommendationAdjudicationRecord,
        adjudication_authorization_digest: str,
        candidate_set: ProtectedRecommendationCandidateSet,
        completion_report: ProtectedCandidateRiskRecoveryReport,
    ) -> tuple[
        ProtectedRecommendationAdjudicationReceipt,
        ProtectedRecommendationAdjudicationReport,
    ]: ...
