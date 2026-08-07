from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentClaim,
    OperationalKnowledgeProtectedContentInstruction,
    OperationalKnowledgeProtectedContentPolicySnapshot,
    OperationalKnowledgeProtectedContentPresenterGrant,
    OperationalKnowledgeProtectedContentRecord,
)
from atlas.modules.knowledge.domain.protected_inspection import (
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
    OperationalKnowledgeProtectedInspectionRecord,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentRecord,
)


class OperationalKnowledgeProtectedContentError(RuntimeError):
    pass


class OperationalKnowledgeProtectedContentUncertainError(OperationalKnowledgeProtectedContentError):
    pass


class OperationalKnowledgeProtectedContentSource(Protocol):
    async def protected_content_source(
        self, *, lease_id: str
    ) -> tuple[
        OperationalKnowledgeProtectedInspectionRecord,
        OperationalKnowledgeProtectedInspectionPolicySnapshot,
        OperationalKnowledgeReviewerAssignmentRecord,
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]: ...


class OperationalKnowledgeProtectedContentPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeProtectedContentPolicySnapshot | None: ...


class OperationalKnowledgeProtectedContentPresenter(Protocol):
    async def present(
        self, instruction: OperationalKnowledgeProtectedContentInstruction
    ) -> OperationalKnowledgeProtectedContentPresenterGrant: ...


class OperationalKnowledgeProtectedContentRepository(Protocol):
    async def get(
        self, *, presentation_id: str
    ) -> OperationalKnowledgeProtectedContentRecord | None: ...

    async def get_by_source_lease(
        self, *, source_lease_id: str
    ) -> OperationalKnowledgeProtectedContentRecord | None: ...

    async def get_claim_by_source_lease(
        self, *, source_lease_id: str
    ) -> OperationalKnowledgeProtectedContentClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeProtectedContentClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeProtectedContentClaim) -> bool: ...

    async def add(self, record: OperationalKnowledgeProtectedContentRecord) -> bool: ...

    async def close(self) -> None: ...


class OperationalKnowledgeProtectedContentPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
