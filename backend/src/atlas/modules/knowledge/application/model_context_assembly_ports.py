from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.model_context_assembly import (
    ProtectedModelContextClaim,
    ProtectedModelContextInstruction,
    ProtectedModelContextPackage,
    ProtectedModelContextPolicySnapshot,
    ProtectedModelContextReceipt,
    ProtectedModelContextRecord,
)
from atlas.modules.knowledge.domain.protected_retrieval import (
    OperationalKnowledgeEvidencePackage,
    OperationalKnowledgeRetrievalResult,
)


class ProtectedModelContextError(RuntimeError):
    pass


class ProtectedModelContextUncertainError(ProtectedModelContextError):
    pass


class ProtectedModelContextRetrievalSource(Protocol):
    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        retrieval_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeRetrievalResult: ...


class ProtectedModelContextPolicySource(Protocol):
    async def get_by_id(self, *, policy_id: str) -> ProtectedModelContextPolicySnapshot | None: ...


class TrustedProtectedModelContextAssembler(Protocol):
    async def assemble(
        self,
        instruction: ProtectedModelContextInstruction,
        evidence: OperationalKnowledgeEvidencePackage,
    ) -> tuple[ProtectedModelContextReceipt, ProtectedModelContextPackage]: ...

    async def rehydrate(
        self,
        *,
        record: ProtectedModelContextRecord,
        authorization_context_digest: str,
    ) -> ProtectedModelContextPackage: ...


class ProtectedModelContextRepository(Protocol):
    async def get(self, *, context_id: str) -> ProtectedModelContextRecord | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedModelContextClaim | None: ...

    async def claim(self, claim: ProtectedModelContextClaim) -> bool: ...
    async def add(self, record: ProtectedModelContextRecord) -> bool: ...
    async def close(self) -> None: ...


class ProtectedModelContextPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
