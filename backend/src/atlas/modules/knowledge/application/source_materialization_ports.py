from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.publication_preparation_ports import (
    OperationalKnowledgePublicationPreparationSource,
)
from atlas.modules.knowledge.domain.publication_preparation import (
    OperationalKnowledgePublicationPreparationRecord,
)
from atlas.modules.knowledge.domain.source_materialization import (
    OperationalKnowledgeSourceMaterializationClaim,
    OperationalKnowledgeSourceMaterializationInstruction,
    OperationalKnowledgeSourceMaterializationPolicySnapshot,
    OperationalKnowledgeSourceMaterializationReceipt,
    OperationalKnowledgeSourceMaterializationRecord,
)


class OperationalKnowledgeSourceMaterializationError(RuntimeError):
    pass


class OperationalKnowledgeSourceMaterializationUncertainError(
    OperationalKnowledgeSourceMaterializationError
):
    pass


class OperationalKnowledgePublicationPreparationRecordSource(Protocol):
    async def source_materialization_preparation(
        self, *, preparation_id: str
    ) -> OperationalKnowledgePublicationPreparationRecord | None: ...


class OperationalKnowledgeSourceMaterializationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeSourceMaterializationPolicySnapshot | None: ...


class OperationalKnowledgeSourceMaterializer(Protocol):
    async def materialize(
        self, instruction: OperationalKnowledgeSourceMaterializationInstruction
    ) -> OperationalKnowledgeSourceMaterializationReceipt: ...


class OperationalKnowledgeSourceMaterializationRepository(Protocol):
    async def get(
        self, *, materialization_id: str
    ) -> OperationalKnowledgeSourceMaterializationRecord | None: ...

    async def get_claim_by_preparation(
        self, *, preparation_id: str
    ) -> OperationalKnowledgeSourceMaterializationClaim | None: ...

    async def claim(self, claim: OperationalKnowledgeSourceMaterializationClaim) -> bool: ...
    async def add(self, record: OperationalKnowledgeSourceMaterializationRecord) -> bool: ...
    async def close(self) -> None: ...


class OperationalKnowledgeSourceMaterializationPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


OperationalKnowledgeSourceLineage = OperationalKnowledgePublicationPreparationSource
