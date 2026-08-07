from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.finding_presentation import (
    OperationalKnowledgeFindingPresentationClaim,
    OperationalKnowledgeFindingPresentationInstruction,
    OperationalKnowledgeFindingPresentationPolicySnapshot,
    OperationalKnowledgeFindingPresentationReceipt,
    OperationalKnowledgeFindingPresentationRecord,
)
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentRecord,
)
from atlas.modules.knowledge.domain.protected_inspection import (
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
    OperationalKnowledgeProtectedInspectionRecord,
)
from atlas.modules.knowledge.domain.review_finding import (
    OperationalKnowledgeReviewFindingPolicySnapshot,
    OperationalKnowledgeReviewFindingRecord,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentRecord,
)


class OperationalKnowledgeFindingPresentationError(RuntimeError):
    pass


class OperationalKnowledgeFindingPresentationUncertainError(
    OperationalKnowledgeFindingPresentationError
):
    pass


class OperationalKnowledgeFindingPresentationSource(Protocol):
    async def finding_presentation_source(
        self, *, finding_packet_id: str
    ) -> tuple[
        OperationalKnowledgeReviewFindingRecord,
        OperationalKnowledgeProtectedContentRecord,
        OperationalKnowledgeProtectedInspectionRecord,
        OperationalKnowledgeProtectedInspectionPolicySnapshot,
        OperationalKnowledgeReviewerAssignmentRecord,
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
        OperationalKnowledgeReviewFindingPolicySnapshot,
    ]: ...


class OperationalKnowledgeFindingPresentationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeFindingPresentationPolicySnapshot | None: ...


class OperationalKnowledgeFindingPresenter(Protocol):
    async def present(
        self, instruction: OperationalKnowledgeFindingPresentationInstruction
    ) -> OperationalKnowledgeFindingPresentationReceipt: ...


class OperationalKnowledgeFindingPresentationRepository(Protocol):
    async def get(
        self, *, finding_presentation_id: str
    ) -> OperationalKnowledgeFindingPresentationRecord | None: ...

    async def get_by_source_finding(
        self, *, source_finding_packet_id: str
    ) -> OperationalKnowledgeFindingPresentationRecord | None: ...

    async def get_claim_by_source_finding(
        self, *, source_finding_packet_id: str
    ) -> OperationalKnowledgeFindingPresentationClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeFindingPresentationClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeFindingPresentationClaim) -> bool: ...

    async def add(self, record: OperationalKnowledgeFindingPresentationRecord) -> bool: ...

    async def close(self) -> None: ...


class OperationalKnowledgeFindingPresentationPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
