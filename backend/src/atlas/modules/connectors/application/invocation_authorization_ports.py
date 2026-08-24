from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.invocation_authorization import (
    ConnectorInvocationAuthorizationPolicySnapshot,
    ConnectorInvocationAuthorizationRecord,
    ConnectorInvocationInputEnvelopeSnapshot,
    ConnectorInvocationProfileSnapshot,
)
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionVerificationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


class ConnectorInvocationAuthorizationError(RuntimeError):
    pass


class ConnectorInvocationAuthorizationSource(Protocol):
    async def capability_invocation_authorization_source(
        self,
        *,
        verification_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[
        ConnectorTargetSessionVerificationRecord,
        ConnectorCapabilityEnablementRecord,
        frozenset[str],
    ]: ...


class ConnectorInvocationProfileSource(Protocol):
    async def get_by_id(self, *, profile_id: str) -> ConnectorInvocationProfileSnapshot | None: ...


class ConnectorInvocationInputEnvelopeSource(Protocol):
    async def get_by_id(
        self, *, envelope_id: str
    ) -> ConnectorInvocationInputEnvelopeSnapshot | None: ...


class ConnectorInvocationAuthorizationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorInvocationAuthorizationPolicySnapshot | None: ...


class ConnectorCapabilityPermissionAuthorizer(Protocol):
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


class ConnectorInvocationAuthorizationRepository(Protocol):
    async def get(
        self, *, authorization_id: str
    ) -> ConnectorInvocationAuthorizationRecord | None: ...

    async def get_by_target_session(
        self, *, source_target_session_verification_id: str
    ) -> ConnectorInvocationAuthorizationRecord | None: ...

    async def get_by_create_key(
        self, *, authorized_by: str, idempotency_key: str
    ) -> ConnectorInvocationAuthorizationRecord | None: ...

    async def add(self, record: ConnectorInvocationAuthorizationRecord) -> bool: ...

    async def close(self) -> None: ...
