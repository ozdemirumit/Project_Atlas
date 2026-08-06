from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.credential_assignment import ConnectorCredentialProfileSnapshot
from atlas.modules.connectors.domain.runtime_activation import (
    ConnectorRuntimeActivationInstruction,
    ConnectorRuntimeActivationPolicySnapshot,
    ConnectorRuntimeActivationProfileSnapshot,
    ConnectorRuntimeActivationReceipt,
    ConnectorRuntimeActivationRecord,
)
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)


class ConnectorRuntimeActivationError(RuntimeError):
    pass


class ConnectorRuntimeActivationSource(Protocol):
    async def runtime_activation_source(
        self, *, authorization_id: str
    ) -> tuple[
        ConnectorSecretBrokerageAuthorizationRecord,
        ConnectorRuntimeTrustGrantRecord,
        ConnectorCredentialProfileSnapshot,
        frozenset[str],
    ]: ...

    async def capability_invocation_source(
        self, *, authorization_id: str
    ) -> tuple[
        ConnectorSecretBrokerageAuthorizationRecord,
        ConnectorRuntimeTrustGrantRecord,
        ConnectorCredentialProfileSnapshot,
        ConnectorCapabilityEnablementRecord,
        frozenset[str],
    ]: ...


class ConnectorRuntimeActivationProfileSource(Protocol):
    async def get_by_id(
        self, *, profile_id: str
    ) -> ConnectorRuntimeActivationProfileSnapshot | None: ...


class ConnectorRuntimeActivationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorRuntimeActivationPolicySnapshot | None: ...


class ConnectorRuntimeActivator(Protocol):
    async def activate(
        self, instruction: ConnectorRuntimeActivationInstruction
    ) -> ConnectorRuntimeActivationReceipt: ...

    async def compensate(self, *, activation_id: str) -> None: ...


class ConnectorRuntimeActivationRepository(Protocol):
    async def get(self, *, activation_id: str) -> ConnectorRuntimeActivationRecord | None: ...

    async def get_by_brokerage_authorization(
        self, *, source_brokerage_authorization_id: str
    ) -> ConnectorRuntimeActivationRecord | None: ...

    async def get_by_create_key(
        self, *, activated_by: str, idempotency_key: str
    ) -> ConnectorRuntimeActivationRecord | None: ...

    async def add(self, record: ConnectorRuntimeActivationRecord) -> bool: ...

    async def close(self) -> None: ...
