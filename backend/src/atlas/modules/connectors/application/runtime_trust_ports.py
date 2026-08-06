from __future__ import annotations

from typing import Protocol

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


class ConnectorRuntimeTrustPolicySource(Protocol):
    async def get_by_id(self, *, policy_id: str) -> ConnectorRuntimeTrustPolicySnapshot | None: ...


class ConnectorRuntimeTrustRepository(Protocol):
    async def get(self, *, grant_id: str) -> ConnectorRuntimeTrustGrantRecord | None: ...

    async def get_by_enablement(
        self, *, source_enablement_id: str
    ) -> ConnectorRuntimeTrustGrantRecord | None: ...

    async def get_by_create_key(
        self, *, granted_by: str, idempotency_key: str
    ) -> ConnectorRuntimeTrustGrantRecord | None: ...

    async def add(self, record: ConnectorRuntimeTrustGrantRecord) -> bool: ...

    async def close(self) -> None: ...
