from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.finding_presentation import (
    OperationalKnowledgeFindingPresentationPolicySnapshot,
    OperationalKnowledgeFindingPresentationRecord,
)
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentRecord,
)
from atlas.modules.knowledge.domain.protected_inspection import (
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
    OperationalKnowledgeProtectedInspectionRecord,
)
from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionClaim,
    OperationalKnowledgeTrackReviewDecisionInstruction,
    OperationalKnowledgeTrackReviewDecisionPolicySnapshot,
    OperationalKnowledgeTrackReviewDecisionReceipt,
    OperationalKnowledgeTrackReviewDecisionRecord,
)
from atlas.modules.knowledge.domain.review_finding import (
    OperationalKnowledgeReviewFindingPolicySnapshot,
    OperationalKnowledgeReviewFindingRecord,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentRecord,
)


class OperationalKnowledgeTrackReviewDecisionError(RuntimeError):
    pass


class OperationalKnowledgeTrackReviewDecisionUncertainError(
    OperationalKnowledgeTrackReviewDecisionError
):
    pass


class OperationalKnowledgeTrackReviewDecisionSource(Protocol):
    async def review_decision_source(
        self, *, finding_presentation_id: str
    ) -> tuple[
        OperationalKnowledgeFindingPresentationRecord,
        OperationalKnowledgeReviewFindingRecord,
        OperationalKnowledgeProtectedContentRecord,
        OperationalKnowledgeProtectedInspectionRecord,
        OperationalKnowledgeProtectedInspectionPolicySnapshot,
        OperationalKnowledgeReviewerAssignmentRecord,
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
        OperationalKnowledgeReviewFindingPolicySnapshot,
        OperationalKnowledgeFindingPresentationPolicySnapshot,
    ]: ...


class OperationalKnowledgeTrackReviewDecisionPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeTrackReviewDecisionPolicySnapshot | None: ...


class OperationalKnowledgeTrackReviewDecisionAttestor(Protocol):
    async def attest(
        self, instruction: OperationalKnowledgeTrackReviewDecisionInstruction
    ) -> OperationalKnowledgeTrackReviewDecisionReceipt: ...


class OperationalKnowledgeTrackReviewDecisionRepository(Protocol):
    async def get(
        self, *, decision_id: str
    ) -> OperationalKnowledgeTrackReviewDecisionRecord | None: ...

    async def get_by_source_presentation(
        self, *, source_finding_presentation_id: str
    ) -> OperationalKnowledgeTrackReviewDecisionRecord | None: ...

    async def get_claim_by_source_presentation(
        self, *, source_finding_presentation_id: str
    ) -> OperationalKnowledgeTrackReviewDecisionClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeTrackReviewDecisionClaim | None: ...

    async def list_by_review_request(
        self,
        *,
        review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...]: ...

    async def claim(self, claim: OperationalKnowledgeTrackReviewDecisionClaim) -> bool: ...

    async def add(self, record: OperationalKnowledgeTrackReviewDecisionRecord) -> bool: ...

    async def close(self) -> None: ...


class OperationalKnowledgeTrackReviewDecisionPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
