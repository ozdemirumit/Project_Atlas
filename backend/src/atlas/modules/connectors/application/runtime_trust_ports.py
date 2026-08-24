from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.application.capability_enablement_ports import (
    ConnectorCapabilityEnablementRepository,
)
from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
)
from atlas.modules.connectors.domain.runtime_trust import (
    ConnectorRuntimeTrustGrantRecord,
    ConnectorRuntimeTrustPolicySnapshot,
    ConnectorRuntimeTrustProfileSnapshot,
)


class ConnectorRuntimeTrustError(RuntimeError):
    pass


class ConnectorRuntimeTrustEnablementSource(Protocol):
    @property
    def repository(self) -> ConnectorCapabilityEnablementRepository: ...

    async def runtime_trust_source(
        self, *, enablement_id: str
    ) -> tuple[
        ConnectorCapabilityEnablementRecord,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]: ...


class ConnectorRuntimeTrustProfileSource(Protocol):
    async def get_by_id(
        self, *, profile_id: str
    ) -> ConnectorRuntimeTrustProfileSnapshot | None: ...

    async def get_by_id_in_scope(
        self,
        *,
        profile_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeTrustProfileSnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeTrustProfileSnapshot, ...]: ...


class ConnectorRuntimeTrustPolicySource(Protocol):
    async def get_by_id(self, *, policy_id: str) -> ConnectorRuntimeTrustPolicySnapshot | None: ...

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeTrustPolicySnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeTrustPolicySnapshot, ...]: ...


class ConnectorRuntimeTrustRepository(Protocol):
    async def get(self, *, grant_id: str) -> ConnectorRuntimeTrustGrantRecord | None: ...

    async def get_in_scope(
        self,
        *,
        grant_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeTrustGrantRecord | None: ...

    async def get_by_enablement(
        self, *, source_enablement_id: str
    ) -> ConnectorRuntimeTrustGrantRecord | None: ...

    async def get_by_enablement_in_scope(
        self,
        *,
        source_enablement_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeTrustGrantRecord | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeTrustGrantRecord, ...]: ...

    async def get_by_create_key(
        self, *, granted_by: str, idempotency_key: str
    ) -> ConnectorRuntimeTrustGrantRecord | None: ...

    async def get_by_create_key_in_scope(
        self,
        *,
        granted_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeTrustGrantRecord | None: ...

    async def add(self, record: ConnectorRuntimeTrustGrantRecord) -> bool: ...

    async def close(self) -> None: ...
