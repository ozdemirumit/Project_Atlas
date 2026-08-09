from __future__ import annotations

from typing import Protocol

from atlas.modules.ai.domain.protected_recommendation_presentation import (
    ProtectedPresentedRecommendation,
    ProtectedRecommendationPresentationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.domain.promotion import (
    PromotedRecommendationArtifact,
    RecommendationPromotionClaim,
    RecommendationPromotionInstruction,
    RecommendationPromotionPolicySnapshot,
    RecommendationPromotionReceipt,
)


class RecommendationPromotionError(RuntimeError):
    pass


class RecommendationPromotionUncertainError(RecommendationPromotionError):
    pass


class RecommendationPromotionRepository(Protocol):
    async def claim(self, claim: RecommendationPromotionClaim) -> bool: ...
    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationPromotionClaim | None: ...
    async def save(self, artifact: PromotedRecommendationArtifact) -> None: ...
    async def get(self, *, recommendation_id: str) -> PromotedRecommendationArtifact | None: ...
    async def close(self) -> None: ...


class RecommendationPromotionPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationPromotionPolicySnapshot | None: ...


class RecommendationPromotionPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedRecommendationPromoter(Protocol):
    async def promote(
        self,
        instruction: RecommendationPromotionInstruction,
        presentation_record: ProtectedRecommendationPresentationRecord,
        presentation: ProtectedPresentedRecommendation,
        *,
        claim_id: str,
        policy_version: str,
        purpose: str,
        classification: str,
        browser_session_binding_digest: str,
    ) -> tuple[RecommendationPromotionReceipt, PromotedRecommendationArtifact]: ...
