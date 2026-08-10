from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.protected_content import (
    RecommendationProtectedContentClaim,
    RecommendationProtectedContentInstruction,
    RecommendationProtectedContentPolicySnapshot,
    RecommendationProtectedContentPresenterGrant,
    RecommendationProtectedContentRecord,
)
from atlas.modules.recommendations.domain.protected_inspection import (
    RecommendationProtectedInspectionPolicySnapshot,
    RecommendationProtectedInspectionRecord,
)
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentPolicySnapshot,
    RecommendationReviewerAssignmentRecord,
)


class RecommendationProtectedContentError(RuntimeError):
    pass


class RecommendationProtectedContentUncertainError(RecommendationProtectedContentError):
    pass


class RecommendationProtectedContentSource(Protocol):
    async def protected_content_source(
        self, *, lease_id: str
    ) -> tuple[
        RecommendationProtectedInspectionRecord,
        RecommendationProtectedInspectionPolicySnapshot,
        RecommendationReviewerAssignmentRecord,
        RecommendationReviewerAssignmentPolicySnapshot,
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
    ]: ...


class RecommendationProtectedContentPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationProtectedContentPolicySnapshot | None: ...


class RecommendationProtectedContentPresenter(Protocol):
    async def present(
        self, instruction: RecommendationProtectedContentInstruction
    ) -> RecommendationProtectedContentPresenterGrant: ...


class RecommendationProtectedContentRepository(Protocol):
    async def get(self, *, presentation_id: str) -> RecommendationProtectedContentRecord | None: ...
    async def get_by_source_lease(
        self, *, source_lease_id: str
    ) -> RecommendationProtectedContentRecord | None: ...
    async def get_claim_by_source_lease(
        self, *, source_lease_id: str
    ) -> RecommendationProtectedContentClaim | None: ...
    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationProtectedContentClaim | None: ...
    async def claim(self, claim: RecommendationProtectedContentClaim) -> bool: ...
    async def add(self, record: RecommendationProtectedContentRecord) -> bool: ...
    async def close(self) -> None: ...


class RecommendationProtectedContentPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
