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
        self, *, invocation_id: str, organization_id: str, environment_id: str
    ) -> tuple[ConnectorBoundedInvocationRecord, frozenset[str]]: ...


class ConnectorInvocationEvidencePolicySource(Protocol):
    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationEvidencePolicySnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationEvidencePolicySnapshot, ...]: ...


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
    async def get_in_scope(
        self, *, ingestion_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationEvidenceRecord | None: ...

    async def get_by_invocation_in_scope(
        self,
        *,
        source_invocation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationEvidenceRecord | None: ...

    async def get_claim_by_invocation_in_scope(
        self,
        *,
        source_invocation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationEvidenceClaim | None: ...

    async def get_claim_by_idempotency_in_scope(
        self,
        *,
        claimed_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationEvidenceClaim | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationEvidenceRecord, ...]: ...

    async def claim(self, claim: ConnectorInvocationEvidenceClaim) -> bool: ...

    async def add(self, record: ConnectorInvocationEvidenceRecord) -> bool: ...

    async def close(self) -> None: ...
