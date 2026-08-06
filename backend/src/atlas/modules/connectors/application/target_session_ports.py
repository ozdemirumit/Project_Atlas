from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.credential_assignment import ConnectorCredentialProfileSnapshot
from atlas.modules.connectors.domain.runtime_activation import ConnectorRuntimeActivationRecord
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionInstruction,
    ConnectorTargetSessionPolicySnapshot,
    ConnectorTargetSessionProfileSnapshot,
    ConnectorTargetSessionReceipt,
    ConnectorTargetSessionVerificationRecord,
)


class ConnectorTargetSessionError(RuntimeError):
    pass


class ConnectorTargetSessionSource(Protocol):
    async def target_session_source(
        self, *, activation_id: str
    ) -> tuple[
        ConnectorRuntimeActivationRecord,
        ConnectorSecretBrokerageAuthorizationRecord,
        ConnectorRuntimeTrustGrantRecord,
        ConnectorCredentialProfileSnapshot,
        frozenset[str],
    ]: ...

    async def capability_invocation_source(
        self, *, activation_id: str
    ) -> tuple[
        ConnectorRuntimeActivationRecord,
        ConnectorCapabilityEnablementRecord,
        frozenset[str],
    ]: ...


class ConnectorTargetSessionProfileSource(Protocol):
    async def get_by_id(
        self, *, profile_id: str
    ) -> ConnectorTargetSessionProfileSnapshot | None: ...


class ConnectorTargetSessionPolicySource(Protocol):
    async def get_by_id(self, *, policy_id: str) -> ConnectorTargetSessionPolicySnapshot | None: ...


class ConnectorTargetSessionAdapter(Protocol):
    async def verify(
        self, instruction: ConnectorTargetSessionInstruction
    ) -> ConnectorTargetSessionReceipt: ...

    async def compensate(self, *, verification_id: str) -> None: ...


class ConnectorTargetSessionRepository(Protocol):
    async def get(
        self, *, verification_id: str
    ) -> ConnectorTargetSessionVerificationRecord | None: ...

    async def get_by_runtime_activation(
        self, *, source_runtime_activation_id: str
    ) -> ConnectorTargetSessionVerificationRecord | None: ...

    async def get_by_create_key(
        self, *, verified_by: str, idempotency_key: str
    ) -> ConnectorTargetSessionVerificationRecord | None: ...

    async def add(self, record: ConnectorTargetSessionVerificationRecord) -> bool: ...

    async def close(self) -> None: ...
