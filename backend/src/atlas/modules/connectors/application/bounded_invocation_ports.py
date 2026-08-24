from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.bounded_invocation import (
    ConnectorBoundedInvocationInstruction,
    ConnectorBoundedInvocationPolicySnapshot,
    ConnectorBoundedInvocationReceipt,
    ConnectorBoundedInvocationRecord,
    ConnectorInvocationConsumptionClaim,
)
from atlas.modules.connectors.domain.invocation_authorization import (
    ConnectorInvocationAuthorizationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


class ConnectorBoundedInvocationError(RuntimeError):
    pass


class ConnectorBoundedInvocationUncertainError(ConnectorBoundedInvocationError):
    pass


class ConnectorBoundedInvocationSource(Protocol):
    async def bounded_invocation_source(
        self, *, authorization_id: str, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationAuthorizationRecord, frozenset[str]]: ...


class ConnectorBoundedInvocationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorBoundedInvocationPolicySnapshot | None: ...


class ConnectorBoundedInvocationAdapter(Protocol):
    async def invoke(
        self, instruction: ConnectorBoundedInvocationInstruction
    ) -> ConnectorBoundedInvocationReceipt: ...


class ConnectorBoundedInvocationPermissionAuthorizer(Protocol):
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


class ConnectorBoundedInvocationRepository(Protocol):
    async def get(self, *, invocation_id: str) -> ConnectorBoundedInvocationRecord | None: ...

    async def get_by_authorization(
        self, *, source_authorization_id: str
    ) -> ConnectorBoundedInvocationRecord | None: ...

    async def get_claim_by_authorization(
        self, *, source_authorization_id: str
    ) -> ConnectorInvocationConsumptionClaim | None: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> ConnectorInvocationConsumptionClaim | None: ...

    async def claim(self, claim: ConnectorInvocationConsumptionClaim) -> bool: ...

    async def add(self, record: ConnectorBoundedInvocationRecord) -> bool: ...

    async def close(self) -> None: ...
