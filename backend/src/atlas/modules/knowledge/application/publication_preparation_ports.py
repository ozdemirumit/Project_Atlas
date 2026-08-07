from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.final_resolution import (
    OperationalKnowledgeFinalResolutionRecord,
)
from atlas.modules.knowledge.domain.publication_preparation import (
    OperationalKnowledgePublicationPreparationClaim,
    OperationalKnowledgePublicationPreparationInstruction,
    OperationalKnowledgePublicationPreparationPolicySnapshot,
    OperationalKnowledgePublicationPreparationReceipt,
    OperationalKnowledgePublicationPreparationRecord,
)
from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionRecord,
)


class OperationalKnowledgePublicationPreparationError(RuntimeError):
    pass


class OperationalKnowledgePublicationPreparationUncertainError(
    OperationalKnowledgePublicationPreparationError
):
    pass


class OperationalKnowledgePublicationPreparationSource(Protocol):
    async def publication_preparation_source(
        self, *, resolution_id: str
    ) -> tuple[
        OperationalKnowledgeFinalResolutionRecord,
        tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]: ...


class OperationalKnowledgePublicationPreparationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgePublicationPreparationPolicySnapshot | None: ...


class OperationalKnowledgePublicationPreparer(Protocol):
    async def prepare(
        self, instruction: OperationalKnowledgePublicationPreparationInstruction
    ) -> OperationalKnowledgePublicationPreparationReceipt: ...


class OperationalKnowledgePublicationPreparationRepository(Protocol):
    async def get(
        self, *, preparation_id: str
    ) -> OperationalKnowledgePublicationPreparationRecord | None: ...

    async def get_by_resolution(
        self, *, resolution_id: str
    ) -> OperationalKnowledgePublicationPreparationRecord | None: ...

    async def get_claim_by_resolution(
        self, *, resolution_id: str
    ) -> OperationalKnowledgePublicationPreparationClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgePublicationPreparationClaim | None: ...

    async def claim(self, claim: OperationalKnowledgePublicationPreparationClaim) -> bool: ...
    async def add(self, record: OperationalKnowledgePublicationPreparationRecord) -> bool: ...
    async def close(self) -> None: ...


class OperationalKnowledgePublicationPreparationPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
