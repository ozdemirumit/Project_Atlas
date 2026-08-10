from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.domain.correction_resubmission import (
    RecommendationCorrectionClaim,
    RecommendationCorrectionInstruction,
    RecommendationCorrectionPolicySnapshot,
    RecommendationCorrectionReceipt,
    RecommendationCorrectionRecord,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_decision import (
    RecommendationTrackReviewDecisionRecord,
)
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord


class RecommendationCorrectionError(RuntimeError):
    pass


class RecommendationCorrectionUncertainError(RecommendationCorrectionError):
    pass


class RecommendationCorrectionSource(Protocol):
    async def correction_resubmission_source(
        self, *, review_request_id: str
    ) -> tuple[
        tuple[RecommendationTrackReviewDecisionRecord, ...],
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
    ]: ...


class RecommendationCorrectionPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationCorrectionPolicySnapshot | None: ...


class RecommendationCorrectionAdapter(Protocol):
    async def correct(
        self,
        instruction: RecommendationCorrectionInstruction,
        source: PromotedRecommendationArtifact,
    ) -> tuple[RecommendationCorrectionReceipt, PromotedRecommendationArtifact]: ...

    async def get_artifact(
        self, *, recommendation_id: str
    ) -> PromotedRecommendationArtifact | None: ...


class RecommendationCorrectionRepository(Protocol):
    async def get(self, *, correction_id: str) -> RecommendationCorrectionRecord | None: ...

    async def get_by_source_request(
        self, *, source_review_request_id: str
    ) -> RecommendationCorrectionRecord | None: ...

    async def get_by_new_recommendation(
        self, *, new_recommendation_id: str
    ) -> RecommendationCorrectionRecord | None: ...

    async def get_claim_by_source_request(
        self, *, source_review_request_id: str
    ) -> RecommendationCorrectionClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationCorrectionClaim | None: ...

    async def claim(self, claim: RecommendationCorrectionClaim) -> bool: ...

    async def add(self, record: RecommendationCorrectionRecord) -> bool: ...

    async def close(self) -> None: ...


class RecommendationCorrectionPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
