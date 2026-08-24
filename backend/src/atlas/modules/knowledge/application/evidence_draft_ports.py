from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.invocation_evidence import ConnectorInvocationEvidenceRecord
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.evidence_draft import (
    OperationalEvidenceKnowledgeDraftClaim,
    OperationalEvidenceKnowledgeDraftInstruction,
    OperationalEvidenceKnowledgeDraftPolicySnapshot,
    OperationalEvidenceKnowledgeDraftReceipt,
    OperationalEvidenceKnowledgeDraftRecord,
)


class OperationalEvidenceKnowledgeDraftError(RuntimeError):
    pass


class OperationalEvidenceKnowledgeDraftUncertainError(OperationalEvidenceKnowledgeDraftError):
    pass


class OperationalEvidenceKnowledgeDraftSource(Protocol):
    async def knowledge_draft_source(
        self, *, ingestion_id: str, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationEvidenceRecord, frozenset[str]]: ...


class OperationalEvidenceKnowledgeDraftPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalEvidenceKnowledgeDraftPolicySnapshot | None: ...


class OperationalEvidenceKnowledgeDraftAdapter(Protocol):
    async def create_draft(
        self, instruction: OperationalEvidenceKnowledgeDraftInstruction
    ) -> OperationalEvidenceKnowledgeDraftReceipt: ...


class OperationalEvidenceKnowledgeDraftRepository(Protocol):
    async def get(self, *, draft_id: str) -> OperationalEvidenceKnowledgeDraftRecord | None: ...

    async def get_by_source(
        self, *, source_ingestion_id: str
    ) -> OperationalEvidenceKnowledgeDraftRecord | None: ...

    async def get_claim_by_source(
        self, *, source_ingestion_id: str
    ) -> OperationalEvidenceKnowledgeDraftClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> OperationalEvidenceKnowledgeDraftClaim | None: ...

    async def claim(self, claim: OperationalEvidenceKnowledgeDraftClaim) -> bool: ...

    async def add(self, record: OperationalEvidenceKnowledgeDraftRecord) -> bool: ...

    async def close(self) -> None: ...


class OperationalEvidenceKnowledgeDraftPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
