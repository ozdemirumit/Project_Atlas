from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.domain.final_disposition import (
    FinalRecommendationDispositionClaim,
    FinalRecommendationDispositionInstruction,
    FinalRecommendationDispositionPolicySnapshot,
    FinalRecommendationDispositionReceipt,
    FinalRecommendationDispositionRecord,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_decision import (
    RecommendationTrackReviewDecisionRecord,
)
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord


class FinalRecommendationDispositionError(RuntimeError):
    pass


class FinalRecommendationDispositionUncertainError(FinalRecommendationDispositionError):
    pass


class FinalRecommendationDispositionSource(Protocol):
    async def final_disposition_source(
        self, *, review_request_id: str
    ) -> tuple[
        tuple[RecommendationTrackReviewDecisionRecord, ...],
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
    ]: ...


class FinalRecommendationDispositionPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> FinalRecommendationDispositionPolicySnapshot | None: ...


class FinalRecommendationDispositionAttestor(Protocol):
    async def attest(
        self, instruction: FinalRecommendationDispositionInstruction
    ) -> FinalRecommendationDispositionReceipt: ...


class FinalRecommendationDispositionRepository(Protocol):
    async def get(self, *, disposition_id: str) -> FinalRecommendationDispositionRecord | None: ...

    async def get_by_review_request(
        self, *, review_request_id: str
    ) -> FinalRecommendationDispositionRecord | None: ...

    async def get_claim_by_review_request(
        self, *, review_request_id: str
    ) -> FinalRecommendationDispositionClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> FinalRecommendationDispositionClaim | None: ...

    async def claim(self, claim: FinalRecommendationDispositionClaim) -> bool: ...

    async def add(self, record: FinalRecommendationDispositionRecord) -> bool: ...

    async def close(self) -> None: ...


class FinalRecommendationDispositionPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
