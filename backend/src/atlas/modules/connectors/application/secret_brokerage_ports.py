from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.credential_assignment import (
    ConnectorCredentialAssignmentRecord,
    ConnectorCredentialProfileSnapshot,
)
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
    ConnectorSecretBrokeragePolicySnapshot,
    ConnectorSecretBrokerageProfileSnapshot,
)


class ConnectorSecretBrokerageError(RuntimeError):
    pass


class ConnectorSecretBrokerageRuntimeTrustSource(Protocol):
    async def secret_brokerage_source(
        self, *, grant_id: str
    ) -> tuple[ConnectorRuntimeTrustGrantRecord, frozenset[str]]: ...


class ConnectorSecretBrokerageCredentialSource(Protocol):
    async def secret_brokerage_source(
        self, *, credential_profile_id: str, instance_id: str
    ) -> tuple[
        ConnectorCredentialAssignmentRecord,
        ConnectorCredentialProfileSnapshot,
        frozenset[str],
    ]: ...


class ConnectorSecretBrokerageProfileSource(Protocol):
    async def get_by_id(
        self, *, profile_id: str
    ) -> ConnectorSecretBrokerageProfileSnapshot | None: ...


class ConnectorSecretBrokeragePolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorSecretBrokeragePolicySnapshot | None: ...


class ConnectorSecretBrokerageRepository(Protocol):
    async def get(
        self, *, authorization_id: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None: ...

    async def get_by_runtime_trust(
        self, *, source_runtime_trust_grant_id: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None: ...

    async def get_by_create_key(
        self, *, authorized_by: str, idempotency_key: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None: ...

    async def add(self, record: ConnectorSecretBrokerageAuthorizationRecord) -> bool: ...

    async def close(self) -> None: ...
