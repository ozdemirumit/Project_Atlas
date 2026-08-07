from __future__ import annotations

from typing import Protocol

from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationClaim,
    ProtectedDraftAdjudicationInstruction,
    ProtectedDraftAdjudicationPolicySnapshot,
    ProtectedDraftAdjudicationReceipt,
    ProtectedDraftAdjudicationRecord,
    ProtectedDraftAdjudicationReport,
)
from atlas.modules.ai.domain.protected_model_invocation import ProtectedModelResponseDraft
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextPackage


class ProtectedDraftAdjudicationError(RuntimeError):
    pass


class ProtectedDraftAdjudicationUncertainError(ProtectedDraftAdjudicationError):
    pass


class ProtectedDraftAdjudicationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedDraftAdjudicationPolicySnapshot | None: ...


class ProtectedDraftAdjudicationRepository(Protocol):
    async def get(self, *, adjudication_id: str) -> ProtectedDraftAdjudicationRecord | None: ...
    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedDraftAdjudicationClaim | None: ...
    async def claim(self, claim: ProtectedDraftAdjudicationClaim) -> bool: ...
    async def add(self, record: ProtectedDraftAdjudicationRecord) -> bool: ...
    async def close(self) -> None: ...


class ProtectedDraftAdjudicationPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedProtectedDraftAdjudicator(Protocol):
    async def adjudicate(
        self,
        instruction: ProtectedDraftAdjudicationInstruction,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedDraftAdjudicationReceipt, ProtectedDraftAdjudicationReport]: ...
    async def rehydrate(
        self, *, record: ProtectedDraftAdjudicationRecord, adjudication_authorization_digest: str
    ) -> ProtectedDraftAdjudicationReport: ...
