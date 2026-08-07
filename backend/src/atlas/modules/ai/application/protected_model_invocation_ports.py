from __future__ import annotations

from typing import Protocol

from atlas.modules.ai.domain.protected_model_invocation import (
    ProtectedModelInvocationClaim,
    ProtectedModelInvocationInstruction,
    ProtectedModelInvocationPolicySnapshot,
    ProtectedModelInvocationReceipt,
    ProtectedModelInvocationRecord,
    ProtectedModelResponseDraft,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextPackage


class ProtectedModelInvocationError(RuntimeError):
    pass


class ProtectedModelInvocationUncertainError(ProtectedModelInvocationError):
    pass


class ProtectedModelInvocationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedModelInvocationPolicySnapshot | None: ...


class ProtectedModelInvocationRepository(Protocol):
    async def get(self, *, invocation_id: str) -> ProtectedModelInvocationRecord | None: ...
    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedModelInvocationClaim | None: ...
    async def claim(self, claim: ProtectedModelInvocationClaim) -> bool: ...
    async def add(self, record: ProtectedModelInvocationRecord) -> bool: ...
    async def close(self) -> None: ...


class ProtectedModelInvocationPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedProtectedModelGateway(Protocol):
    async def invoke(
        self,
        instruction: ProtectedModelInvocationInstruction,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedModelInvocationReceipt, ProtectedModelResponseDraft]: ...
    async def rehydrate(
        self, *, record: ProtectedModelInvocationRecord, invocation_authorization_digest: str
    ) -> ProtectedModelResponseDraft: ...
