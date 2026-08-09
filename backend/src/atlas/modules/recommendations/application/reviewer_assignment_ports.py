from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentClaim,
    RecommendationReviewerAssignmentInstruction,
    RecommendationReviewerAssignmentPolicySnapshot,
    RecommendationReviewerAssignmentReceipt,
    RecommendationReviewerAssignmentRecord,
)


class RecommendationReviewerAssignmentError(Exception):
    pass


class RecommendationReviewerAssignmentUncertainError(RecommendationReviewerAssignmentError):
    pass


class RecommendationReviewerAssignmentRepository(Protocol):
    async def claim(self, claim: RecommendationReviewerAssignmentClaim) -> bool: ...
    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationReviewerAssignmentClaim | None: ...
    async def save(self, record: RecommendationReviewerAssignmentRecord) -> None: ...
    async def get(
        self, *, assignment_set_id: str
    ) -> RecommendationReviewerAssignmentRecord | None: ...
    async def close(self) -> None: ...


class RecommendationReviewerAssignmentPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationReviewerAssignmentPolicySnapshot | None: ...


class RecommendationReviewerAssignmentPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        permission_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedRecommendationReviewerAssignmentAdapter(Protocol):
    async def assign(
        self,
        instruction: RecommendationReviewerAssignmentInstruction,
        source: RecommendationReviewRequestRecord,
    ) -> RecommendationReviewerAssignmentReceipt: ...
