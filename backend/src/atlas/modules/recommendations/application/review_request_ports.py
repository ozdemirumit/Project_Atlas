from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_request import (
    RecommendationReviewRequestClaim,
    RecommendationReviewRequestInstruction,
    RecommendationReviewRequestPolicySnapshot,
    RecommendationReviewRequestReceipt,
    RecommendationReviewRequestRecord,
)


class RecommendationReviewRequestError(Exception):
    pass


class RecommendationReviewRequestUncertainError(RecommendationReviewRequestError):
    pass


class RecommendationReviewRequestRepository(Protocol):
    async def claim(self, claim: RecommendationReviewRequestClaim) -> bool: ...
    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationReviewRequestClaim | None: ...
    async def save(self, record: RecommendationReviewRequestRecord) -> None: ...
    async def get(self, *, review_request_id: str) -> RecommendationReviewRequestRecord | None: ...
    async def close(self) -> None: ...


class RecommendationReviewRequestPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationReviewRequestPolicySnapshot | None: ...


class RecommendationReviewRequestPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedRecommendationReviewRequestOrchestrator(Protocol):
    async def orchestrate(
        self,
        instruction: RecommendationReviewRequestInstruction,
        source: RecommendationReadinessAssessment,
        *,
        claim_id: str,
        policy_version: str,
        purpose: str,
        classification: str,
        browser_session_binding_digest: str,
    ) -> tuple[RecommendationReviewRequestReceipt, RecommendationReviewRequestRecord]: ...
