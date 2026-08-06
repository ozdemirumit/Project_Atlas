from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.bounded_invocation import ConnectorBoundedInvocationRecord
from atlas.modules.connectors.domain.invocation_evidence import (
    ConnectorInvocationEvidenceClaim,
    ConnectorInvocationEvidenceInstruction,
    ConnectorInvocationEvidencePolicySnapshot,
    ConnectorInvocationEvidenceReceipt,
    ConnectorInvocationEvidenceRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


class ConnectorInvocationEvidenceError(RuntimeError):
    pass


class ConnectorInvocationEvidenceUncertainError(ConnectorInvocationEvidenceError):
    pass


class ConnectorInvocationEvidenceSource(Protocol):
    async def evidence_ingestion_source(
        self, *, invocation_id: str
    ) -> tuple[ConnectorBoundedInvocationRecord, frozenset[str]]: ...


class ConnectorInvocationEvidencePolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorInvocationEvidencePolicySnapshot | None: ...


class ConnectorInvocationEvidenceAdapter(Protocol):
    async def ingest(
        self, instruction: ConnectorInvocationEvidenceInstruction
    ) -> ConnectorInvocationEvidenceReceipt: ...


class ConnectorInvocationEvidencePermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        permission_id: str,
        capability_id: str,
        capability_class: str,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class ConnectorInvocationEvidenceRepository(Protocol):
    async def get(self, *, ingestion_id: str) -> ConnectorInvocationEvidenceRecord | None: ...

    async def get_by_invocation(
        self, *, source_invocation_id: str
    ) -> ConnectorInvocationEvidenceRecord | None: ...

    async def get_claim_by_invocation(
        self, *, source_invocation_id: str
    ) -> ConnectorInvocationEvidenceClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> ConnectorInvocationEvidenceClaim | None: ...

    async def claim(self, claim: ConnectorInvocationEvidenceClaim) -> bool: ...

    async def add(self, record: ConnectorInvocationEvidenceRecord) -> bool: ...

    async def close(self) -> None: ...
