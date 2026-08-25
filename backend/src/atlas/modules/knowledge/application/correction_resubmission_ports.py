from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.correction_resubmission import (
    OperationalKnowledgeCorrectionClaim,
    OperationalKnowledgeCorrectionInstruction,
    OperationalKnowledgeCorrectionPolicySnapshot,
    OperationalKnowledgeCorrectionReceipt,
    OperationalKnowledgeCorrectionRecord,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionRecord,
)


class OperationalKnowledgeCorrectionError(RuntimeError):
    pass


class OperationalKnowledgeCorrectionUncertainError(OperationalKnowledgeCorrectionError):
    pass


class OperationalKnowledgeCorrectionSource(Protocol):
    async def correction_resubmission_source(
        self,
        *,
        review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[
        tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]: ...


class OperationalKnowledgeCorrectionPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeCorrectionPolicySnapshot | None: ...


class OperationalKnowledgeCorrectionAdapter(Protocol):
    async def correct_and_resubmit(
        self, instruction: OperationalKnowledgeCorrectionInstruction
    ) -> OperationalKnowledgeCorrectionReceipt: ...


class OperationalKnowledgeCorrectionRepository(Protocol):
    async def get(self, *, correction_id: str) -> OperationalKnowledgeCorrectionRecord | None: ...

    async def get_by_source_request(
        self, *, source_review_request_id: str
    ) -> OperationalKnowledgeCorrectionRecord | None: ...

    async def get_by_new_review_request(
        self,
        *,
        new_review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeCorrectionRecord | None: ...

    async def get_claim_by_source_request(
        self, *, source_review_request_id: str
    ) -> OperationalKnowledgeCorrectionClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeCorrectionClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeCorrectionClaim) -> bool: ...

    async def add(self, record: OperationalKnowledgeCorrectionRecord) -> bool: ...

    async def close(self) -> None: ...


class OperationalKnowledgeCorrectionPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
