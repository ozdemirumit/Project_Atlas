from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.application.runtime_trust_ports import ConnectorRuntimeTrustRepository
from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
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
    @property
    def repository(self) -> ConnectorRuntimeTrustRepository: ...

    async def secret_brokerage_source(
        self, *, grant_id: str
    ) -> tuple[ConnectorRuntimeTrustGrantRecord, frozenset[str]]: ...

    async def capability_invocation_source(
        self, *, grant_id: str
    ) -> tuple[
        ConnectorRuntimeTrustGrantRecord,
        ConnectorCapabilityEnablementRecord,
        frozenset[str],
    ]: ...


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

    async def get_by_id_in_scope(
        self,
        *,
        profile_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorSecretBrokerageProfileSnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorSecretBrokerageProfileSnapshot, ...]: ...


class ConnectorSecretBrokeragePolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorSecretBrokeragePolicySnapshot | None: ...

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorSecretBrokeragePolicySnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorSecretBrokeragePolicySnapshot, ...]: ...


class ConnectorSecretBrokerageRepository(Protocol):
    async def get(
        self, *, authorization_id: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None: ...

    async def get_in_scope(
        self,
        *,
        authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None: ...

    async def get_by_runtime_trust(
        self, *, source_runtime_trust_grant_id: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None: ...

    async def get_by_runtime_trust_in_scope(
        self,
        *,
        source_runtime_trust_grant_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorSecretBrokerageAuthorizationRecord, ...]: ...

    async def get_by_create_key(
        self, *, authorized_by: str, idempotency_key: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None: ...

    async def get_by_create_key_in_scope(
        self,
        *,
        authorized_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None: ...

    async def add(self, record: ConnectorSecretBrokerageAuthorizationRecord) -> bool: ...

    async def close(self) -> None: ...
