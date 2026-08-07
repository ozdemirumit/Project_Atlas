from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.final_resolution import (
    OperationalKnowledgeFinalResolutionClaim,
    OperationalKnowledgeFinalResolutionInstruction,
    OperationalKnowledgeFinalResolutionPolicySnapshot,
    OperationalKnowledgeFinalResolutionReceipt,
    OperationalKnowledgeFinalResolutionRecord,
)
from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionRecord,
)


class OperationalKnowledgeFinalResolutionError(RuntimeError):
    pass


class OperationalKnowledgeFinalResolutionUncertainError(OperationalKnowledgeFinalResolutionError):
    pass


class OperationalKnowledgeFinalResolutionSource(Protocol):
    async def final_resolution_source(
        self, *, review_request_id: str
    ) -> tuple[
        tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]: ...


class OperationalKnowledgeFinalResolutionPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeFinalResolutionPolicySnapshot | None: ...


class OperationalKnowledgeFinalResolutionAttestor(Protocol):
    async def attest(
        self, instruction: OperationalKnowledgeFinalResolutionInstruction
    ) -> OperationalKnowledgeFinalResolutionReceipt: ...


class OperationalKnowledgeFinalResolutionRepository(Protocol):
    async def get(
        self, *, resolution_id: str
    ) -> OperationalKnowledgeFinalResolutionRecord | None: ...

    async def get_by_review_request(
        self, *, review_request_id: str
    ) -> OperationalKnowledgeFinalResolutionRecord | None: ...

    async def get_claim_by_review_request(
        self, *, review_request_id: str
    ) -> OperationalKnowledgeFinalResolutionClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeFinalResolutionClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeFinalResolutionClaim) -> bool: ...
    async def add(self, record: OperationalKnowledgeFinalResolutionRecord) -> bool: ...
    async def close(self) -> None: ...


class OperationalKnowledgeFinalResolutionPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
