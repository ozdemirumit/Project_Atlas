from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.domain.promotion import (
    PromotedRecommendationArtifact,
    RecommendationPromotionResult,
)
from atlas.modules.recommendations.domain.readiness import (
    RecommendationReadinessAssessment,
    RecommendationReadinessClaim,
    RecommendationReadinessInstruction,
    RecommendationReadinessPolicySnapshot,
    RecommendationReadinessReceipt,
)


class RecommendationReadinessError(RuntimeError):
    pass


class RecommendationReadinessUncertainError(RecommendationReadinessError):
    pass


class RecommendationReadinessPromotionSource(Protocol):
    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationPromotionResult: ...

    async def protected_content_source(
        self, *, recommendation_id: str
    ) -> PromotedRecommendationArtifact: ...


class RecommendationReadinessRepository(Protocol):
    async def claim(self, claim: RecommendationReadinessClaim) -> bool: ...
    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationReadinessClaim | None: ...
    async def save(self, assessment: RecommendationReadinessAssessment) -> None: ...
    async def get(self, *, assessment_id: str) -> RecommendationReadinessAssessment | None: ...
    async def close(self) -> None: ...


class RecommendationReadinessPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationReadinessPolicySnapshot | None: ...


class RecommendationReadinessPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedRecommendationReadinessEvaluator(Protocol):
    async def evaluate(
        self,
        instruction: RecommendationReadinessInstruction,
        source: PromotedRecommendationArtifact,
        *,
        claim_id: str,
        policy_version: str,
        purpose: str,
        classification: str,
        browser_session_binding_digest: str,
    ) -> tuple[RecommendationReadinessReceipt, RecommendationReadinessAssessment]: ...
