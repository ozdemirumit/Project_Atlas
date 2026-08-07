from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.source_materialization_ports import (
    OperationalKnowledgePublicationPreparationRecordSource,
    OperationalKnowledgeSourceLineage,
)
from atlas.modules.knowledge.domain.deterministic_chunking import (
    OperationalKnowledgeChunkingClaim,
    OperationalKnowledgeChunkingInstruction,
    OperationalKnowledgeChunkingPolicySnapshot,
    OperationalKnowledgeChunkingReceipt,
    OperationalKnowledgeChunkingRecord,
)
from atlas.modules.knowledge.domain.source_materialization import (
    OperationalKnowledgeSourceMaterializationRecord,
)


class OperationalKnowledgeChunkingError(RuntimeError):
    pass


class OperationalKnowledgeChunkingUncertainError(OperationalKnowledgeChunkingError):
    pass


class OperationalKnowledgeSourceMaterializationRecordSource(Protocol):
    async def source_for_chunking(
        self, *, materialization_id: str
    ) -> OperationalKnowledgeSourceMaterializationRecord | None: ...


class OperationalKnowledgeChunkingPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeChunkingPolicySnapshot | None: ...


class OperationalKnowledgeChunker(Protocol):
    async def chunk(
        self, instruction: OperationalKnowledgeChunkingInstruction
    ) -> OperationalKnowledgeChunkingReceipt: ...


class OperationalKnowledgeChunkingRepository(Protocol):
    async def get(self, *, chunk_set_id: str) -> OperationalKnowledgeChunkingRecord | None: ...

    async def get_claim_by_materialization(
        self, *, materialization_id: str
    ) -> OperationalKnowledgeChunkingClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeChunkingClaim) -> bool: ...
    async def add(self, record: OperationalKnowledgeChunkingRecord) -> bool: ...
    async def close(self) -> None: ...


class OperationalKnowledgeChunkingPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


OperationalKnowledgeChunkingPreparationSource = (
    OperationalKnowledgePublicationPreparationRecordSource
)
OperationalKnowledgeChunkingLineage = OperationalKnowledgeSourceLineage
