from __future__ import annotations

from typing import Protocol

from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactReport,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryReport,
)
from atlas.modules.ai.domain.protected_recommendation_adjudication import (
    ProtectedRecommendationAdjudicationReport,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateSet,
)
from atlas.modules.ai.domain.protected_recommendation_presentation import (
    ProtectedPresentedRecommendation,
    ProtectedRecommendationPresentationClaim,
    ProtectedRecommendationPresentationInstruction,
    ProtectedRecommendationPresentationPolicySnapshot,
    ProtectedRecommendationPresentationReceipt,
    ProtectedRecommendationPresentationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


class ProtectedRecommendationPresentationError(RuntimeError):
    pass


class ProtectedRecommendationPresentationUncertainError(ProtectedRecommendationPresentationError):
    pass


class ProtectedRecommendationPresentationRepository(Protocol):
    async def claim(self, claim: ProtectedRecommendationPresentationClaim) -> bool: ...
    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedRecommendationPresentationClaim | None: ...
    async def save(self, record: ProtectedRecommendationPresentationRecord) -> None: ...
    async def get(
        self, *, presentation_id: str
    ) -> ProtectedRecommendationPresentationRecord | None: ...
    async def close(self) -> None: ...


class ProtectedRecommendationPresentationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedRecommendationPresentationPolicySnapshot | None: ...


class ProtectedRecommendationPresentationPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedProtectedRecommendationPresenter(Protocol):
    async def present(
        self,
        instruction: ProtectedRecommendationPresentationInstruction,
        adjudication_report: ProtectedRecommendationAdjudicationReport,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        completion_report: ProtectedCandidateRiskRecoveryReport,
    ) -> tuple[ProtectedRecommendationPresentationReceipt, ProtectedPresentedRecommendation]: ...

    async def rehydrate(
        self,
        *,
        record: ProtectedRecommendationPresentationRecord,
        presentation_authorization_digest: str,
        adjudication_report: ProtectedRecommendationAdjudicationReport,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        completion_report: ProtectedCandidateRiskRecoveryReport,
    ) -> ProtectedPresentedRecommendation: ...
