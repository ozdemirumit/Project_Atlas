from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentRecord,
)
from atlas.modules.knowledge.domain.protected_inspection import (
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
    OperationalKnowledgeProtectedInspectionRecord,
)
from atlas.modules.knowledge.domain.review_finding import (
    OperationalKnowledgeReviewFindingClaim,
    OperationalKnowledgeReviewFindingInstruction,
    OperationalKnowledgeReviewFindingPolicySnapshot,
    OperationalKnowledgeReviewFindingReceipt,
    OperationalKnowledgeReviewFindingRecord,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentRecord,
)


class OperationalKnowledgeReviewFindingError(RuntimeError):
    pass


class OperationalKnowledgeReviewFindingUncertainError(OperationalKnowledgeReviewFindingError):
    pass


class OperationalKnowledgeReviewFindingSource(Protocol):
    async def review_finding_source(
        self, *, presentation_id: str
    ) -> tuple[
        OperationalKnowledgeProtectedContentRecord,
        OperationalKnowledgeProtectedInspectionRecord,
        OperationalKnowledgeProtectedInspectionPolicySnapshot,
        OperationalKnowledgeReviewerAssignmentRecord,
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]: ...


class OperationalKnowledgeReviewFindingPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeReviewFindingPolicySnapshot | None: ...


class OperationalKnowledgeReviewFindingRecorder(Protocol):
    async def record(
        self, instruction: OperationalKnowledgeReviewFindingInstruction
    ) -> OperationalKnowledgeReviewFindingReceipt: ...


class OperationalKnowledgeReviewFindingRepository(Protocol):
    async def get(
        self, *, finding_packet_id: str
    ) -> OperationalKnowledgeReviewFindingRecord | None: ...

    async def get_by_source_presentation(
        self, *, source_presentation_id: str
    ) -> OperationalKnowledgeReviewFindingRecord | None: ...

    async def get_claim_by_source_presentation(
        self, *, source_presentation_id: str
    ) -> OperationalKnowledgeReviewFindingClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeReviewFindingClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeReviewFindingClaim) -> bool: ...

    async def add(self, record: OperationalKnowledgeReviewFindingRecord) -> bool: ...

    async def close(self) -> None: ...


class OperationalKnowledgeReviewFindingPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
