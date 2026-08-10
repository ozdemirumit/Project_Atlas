from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.domain.finding_presentation import (
    RecommendationFindingPresentationPolicySnapshot,
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
from atlas.modules.recommendations.domain.review_decision import (
    RecommendationTrackReviewDecisionClaim,
    RecommendationTrackReviewDecisionInstruction,
    RecommendationTrackReviewDecisionPolicySnapshot,
    RecommendationTrackReviewDecisionReceipt,
    RecommendationTrackReviewDecisionRecord,
)
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentRecord,
)


class RecommendationTrackReviewDecisionError(RuntimeError):
    pass


class RecommendationTrackReviewDecisionUncertainError(RecommendationTrackReviewDecisionError):
    pass


class RecommendationTrackReviewDecisionSource(Protocol):
    async def review_decision_source(
        self, *, finding_presentation_id: str
    ) -> tuple[
        RecommendationFindingPresentationRecord,
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
        RecommendationFindingPresentationPolicySnapshot,
    ]: ...


class RecommendationTrackReviewDecisionPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationTrackReviewDecisionPolicySnapshot | None: ...


class RecommendationTrackReviewDecisionAttestor(Protocol):
    async def attest(
        self, instruction: RecommendationTrackReviewDecisionInstruction
    ) -> RecommendationTrackReviewDecisionReceipt: ...


class RecommendationTrackReviewDecisionRepository(Protocol):
    async def get(self, *, decision_id: str) -> RecommendationTrackReviewDecisionRecord | None: ...

    async def get_by_source_presentation(
        self, *, source_finding_presentation_id: str
    ) -> RecommendationTrackReviewDecisionRecord | None: ...

    async def get_claim_by_source_presentation(
        self, *, source_finding_presentation_id: str
    ) -> RecommendationTrackReviewDecisionClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationTrackReviewDecisionClaim | None: ...

    async def list_by_review_request(
        self, *, review_request_id: str
    ) -> tuple[RecommendationTrackReviewDecisionRecord, ...]: ...

    async def claim(self, claim: RecommendationTrackReviewDecisionClaim) -> bool: ...

    async def add(self, record: RecommendationTrackReviewDecisionRecord) -> bool: ...

    async def close(self) -> None: ...


class RecommendationTrackReviewDecisionPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
