from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.protected_inspection import (
    OperationalKnowledgeProtectedInspectionBrokerGrant,
    OperationalKnowledgeProtectedInspectionClaim,
    OperationalKnowledgeProtectedInspectionInstruction,
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
    OperationalKnowledgeProtectedInspectionRecord,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    OperationalKnowledgeReviewerAssignmentRecord,
)


class OperationalKnowledgeProtectedInspectionError(RuntimeError):
    pass


class OperationalKnowledgeProtectedInspectionUncertainError(
    OperationalKnowledgeProtectedInspectionError
):
    pass


class OperationalKnowledgeProtectedInspectionSource(Protocol):
    async def protected_inspection_source(
        self, *, assignment_set_id: str
    ) -> tuple[
        OperationalKnowledgeReviewerAssignmentRecord,
        OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    ]: ...


class OperationalKnowledgeProtectedInspectionPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeProtectedInspectionPolicySnapshot | None: ...


class OperationalKnowledgeProtectedInspectionBroker(Protocol):
    async def issue(
        self, instruction: OperationalKnowledgeProtectedInspectionInstruction
    ) -> OperationalKnowledgeProtectedInspectionBrokerGrant: ...


class OperationalKnowledgeProtectedInspectionRepository(Protocol):
    async def get(
        self, *, lease_id: str
    ) -> OperationalKnowledgeProtectedInspectionRecord | None: ...

    async def get_by_source_track(
        self, *, source_assignment_set_id: str, track_code: str
    ) -> OperationalKnowledgeProtectedInspectionRecord | None: ...

    async def get_claim_by_source_track(
        self, *, source_assignment_set_id: str, track_code: str
    ) -> OperationalKnowledgeProtectedInspectionClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeProtectedInspectionClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeProtectedInspectionClaim) -> bool: ...

    async def add(self, record: OperationalKnowledgeProtectedInspectionRecord) -> bool: ...

    async def close(self) -> None: ...


class OperationalKnowledgeProtectedInspectionPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
