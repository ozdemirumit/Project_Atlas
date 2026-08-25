from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestClaim,
    OperationalKnowledgeReviewRequestInstruction,
    OperationalKnowledgeReviewRequestPolicySnapshot,
    OperationalKnowledgeReviewRequestReceipt,
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord


class OperationalKnowledgeReviewRequestError(RuntimeError):
    pass


class OperationalKnowledgeReviewRequestUncertainError(OperationalKnowledgeReviewRequestError):
    pass


class OperationalKnowledgeReviewRequestSource(Protocol):
    async def review_request_source(
        self, *, draft_id: str, organization_id: str, environment_id: str
    ) -> OperationalEvidenceKnowledgeDraftRecord: ...


class OperationalKnowledgeReviewRequestPolicySource(Protocol):
    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewRequestPolicySnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[OperationalKnowledgeReviewRequestPolicySnapshot, ...]: ...


class OperationalKnowledgeReviewRequestAdapter(Protocol):
    available: bool
    adapter_id: str
    attestor_id: str

    async def create_review_request(
        self, instruction: OperationalKnowledgeReviewRequestInstruction
    ) -> OperationalKnowledgeReviewRequestReceipt: ...


class OperationalKnowledgeReviewRequestRepository(Protocol):
    async def get_in_scope(
        self,
        *,
        review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewRequestRecord | None: ...

    async def get_by_source_in_scope(
        self,
        *,
        source_draft_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewRequestRecord | None: ...

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_draft_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewRequestClaim | None: ...

    async def get_claim_by_idempotency_in_scope(
        self,
        *,
        claimed_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewRequestClaim | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[OperationalKnowledgeReviewRequestRecord, ...]: ...

    async def claim(self, claim: OperationalKnowledgeReviewRequestClaim) -> bool: ...

    async def add(self, record: OperationalKnowledgeReviewRequestRecord) -> bool: ...

    async def close(self) -> None: ...


class OperationalKnowledgeReviewRequestPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
