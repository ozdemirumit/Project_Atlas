from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentClaim,
    OperationalKnowledgeReviewerAssignmentInstruction,
    OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    OperationalKnowledgeReviewerAssignmentReceipt,
    OperationalKnowledgeReviewerAssignmentRecord,
)


class OperationalKnowledgeReviewerAssignmentError(RuntimeError):
    pass


class OperationalKnowledgeReviewerAssignmentUncertainError(
    OperationalKnowledgeReviewerAssignmentError
):
    pass


class OperationalKnowledgeReviewerAssignmentSource(Protocol):
    async def reviewer_assignment_source(
        self, *, review_request_id: str, organization_id: str, environment_id: str
    ) -> tuple[OperationalKnowledgeReviewRequestRecord, frozenset[str]]: ...

    async def protected_content_lineage(
        self, *, review_request_id: str, organization_id: str, environment_id: str
    ) -> tuple[
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]: ...


class OperationalKnowledgeReviewerAssignmentPolicySource(Protocol):
    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentPolicySnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[OperationalKnowledgeReviewerAssignmentPolicySnapshot, ...]: ...


class OperationalKnowledgeReviewerAssignmentAdapter(Protocol):
    available: bool
    adapter_id: str
    attestor_id: str

    async def assign_reviewers(
        self, instruction: OperationalKnowledgeReviewerAssignmentInstruction
    ) -> OperationalKnowledgeReviewerAssignmentReceipt: ...


class OperationalKnowledgeReviewerAssignmentRepository(Protocol):
    async def get_in_scope(
        self,
        *,
        assignment_set_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord | None: ...

    async def get_by_source_in_scope(
        self,
        *,
        source_review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord | None: ...

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentClaim | None: ...

    async def get_claim_by_idempotency_in_scope(
        self,
        *,
        claimed_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentClaim | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[OperationalKnowledgeReviewerAssignmentRecord, ...]: ...

    async def claim(self, claim: OperationalKnowledgeReviewerAssignmentClaim) -> bool: ...

    async def add(self, record: OperationalKnowledgeReviewerAssignmentRecord) -> bool: ...

    async def close(self) -> None: ...


class OperationalKnowledgeReviewerAssignmentPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
