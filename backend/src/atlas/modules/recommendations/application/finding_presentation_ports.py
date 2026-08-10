from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.domain.finding_presentation import (
    RecommendationFindingPresentationClaim,
    RecommendationFindingPresentationInstruction,
    RecommendationFindingPresentationPolicySnapshot,
    RecommendationFindingPresentationReceipt,
    RecommendationFindingPresentationRecord,
)
from atlas.modules.recommendations.domain.human_review_finding import (
    RecommendationHumanReviewFindingPolicySnapshot,
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


class RecommendationFindingPresentationError(RuntimeError):
    pass


class RecommendationFindingPresentationUncertainError(RecommendationFindingPresentationError):
    pass


class RecommendationFindingPresentationSource(Protocol):
    async def finding_presentation_source(
        self, *, finding_packet_id: str
    ) -> tuple[
        RecommendationHumanReviewFindingRecord,
        RecommendationProtectedContentRecord,
        RecommendationProtectedInspectionRecord,
        RecommendationProtectedInspectionPolicySnapshot,
        RecommendationReviewerAssignmentRecord,
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
        RecommendationProtectedContentPolicySnapshot,
        RecommendationHumanReviewFindingPolicySnapshot,
    ]: ...


class RecommendationFindingPresentationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationFindingPresentationPolicySnapshot | None: ...


class RecommendationFindingPresenter(Protocol):
    async def present(
        self, instruction: RecommendationFindingPresentationInstruction
    ) -> RecommendationFindingPresentationReceipt: ...


class RecommendationFindingPresentationRepository(Protocol):
    async def get(
        self, *, finding_presentation_id: str
    ) -> RecommendationFindingPresentationRecord | None: ...

    async def get_by_source_finding(
        self, *, source_finding_packet_id: str
    ) -> RecommendationFindingPresentationRecord | None: ...

    async def get_claim_by_source_finding(
        self, *, source_finding_packet_id: str
    ) -> RecommendationFindingPresentationClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationFindingPresentationClaim | None: ...

    async def claim(self, claim: RecommendationFindingPresentationClaim) -> bool: ...

    async def add(self, record: RecommendationFindingPresentationRecord) -> bool: ...

    async def close(self) -> None: ...


class RecommendationFindingPresentationPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
