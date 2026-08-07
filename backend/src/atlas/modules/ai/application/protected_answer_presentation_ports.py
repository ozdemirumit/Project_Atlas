from __future__ import annotations

from typing import Protocol

from atlas.modules.ai.domain.protected_answer_presentation import (
    ProtectedAnswerPresentationClaim,
    ProtectedAnswerPresentationInstruction,
    ProtectedAnswerPresentationPolicySnapshot,
    ProtectedAnswerPresentationReceipt,
    ProtectedAnswerPresentationRecord,
    ProtectedPresentedAnswer,
)
from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationReport,
)
from atlas.modules.ai.domain.protected_model_invocation import ProtectedModelResponseDraft
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextPackage


class ProtectedAnswerPresentationError(RuntimeError):
    pass


class ProtectedAnswerPresentationUncertainError(ProtectedAnswerPresentationError):
    pass


class ProtectedAnswerPresentationRepository(Protocol):
    async def claim(self, claim: ProtectedAnswerPresentationClaim) -> bool: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedAnswerPresentationClaim | None: ...

    async def get_claim_by_adjudication(
        self, *, adjudication_id: str
    ) -> ProtectedAnswerPresentationClaim | None: ...

    async def save(self, record: ProtectedAnswerPresentationRecord) -> None: ...

    async def get(self, *, presentation_id: str) -> ProtectedAnswerPresentationRecord | None: ...

    async def close(self) -> None: ...


class ProtectedAnswerPresentationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedAnswerPresentationPolicySnapshot | None: ...


class ProtectedAnswerPresentationPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedProtectedAnswerPresenter(Protocol):
    async def present(
        self,
        instruction: ProtectedAnswerPresentationInstruction,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedAnswerPresentationReceipt, ProtectedPresentedAnswer]: ...

    async def rehydrate(
        self,
        *,
        record: ProtectedAnswerPresentationRecord,
        presentation_authorization_digest: str,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> ProtectedPresentedAnswer: ...
