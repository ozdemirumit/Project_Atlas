from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.domain.human_review_finding import (
    RecommendationHumanReviewFindingClaim,
    RecommendationHumanReviewFindingInstruction,
    RecommendationHumanReviewFindingPolicySnapshot,
    RecommendationHumanReviewFindingReceipt,
    RecommendationHumanReviewFindingRecord,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.protected_content import (
    RecommendationProtectedContentPolicySnapshot,
    RecommendationProtectedContentRecord,
)
from atlas.modules.recommendations.domain.protected_inspection import (
    RecommendationProtectedInspectionPolicySnapshot,
    RecommendationProtectedInspectionRecord,
)
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentRecord,
)


class RecommendationHumanReviewFindingError(RuntimeError):
    pass


class RecommendationHumanReviewFindingUncertainError(RecommendationHumanReviewFindingError):
    pass


class RecommendationHumanReviewFindingSource(Protocol):
    async def human_review_finding_source(
        self, *, presentation_id: str
    ) -> tuple[
        RecommendationProtectedContentRecord,
        RecommendationProtectedInspectionRecord,
        RecommendationProtectedInspectionPolicySnapshot,
        RecommendationReviewerAssignmentRecord,
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
        RecommendationProtectedContentPolicySnapshot,
    ]: ...


class RecommendationHumanReviewFindingPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationHumanReviewFindingPolicySnapshot | None: ...


class RecommendationHumanReviewFindingRecorder(Protocol):
    async def record(
        self, instruction: RecommendationHumanReviewFindingInstruction
    ) -> RecommendationHumanReviewFindingReceipt: ...


class RecommendationHumanReviewFindingRepository(Protocol):
    async def get(
        self, *, finding_packet_id: str
    ) -> RecommendationHumanReviewFindingRecord | None: ...

    async def get_by_source_presentation(
        self, *, source_presentation_id: str
    ) -> RecommendationHumanReviewFindingRecord | None: ...

    async def get_claim_by_source_presentation(
        self, *, source_presentation_id: str
    ) -> RecommendationHumanReviewFindingClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationHumanReviewFindingClaim | None: ...

    async def claim(self, claim: RecommendationHumanReviewFindingClaim) -> bool: ...

    async def add(self, record: RecommendationHumanReviewFindingRecord) -> bool: ...

    async def close(self) -> None: ...


class RecommendationHumanReviewFindingPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
