from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.instance_creation import (
    ConnectorInstanceCreationPolicySnapshot,
    ConnectorInstanceRecord,
)
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationPolicySnapshot,
    ConnectorPackageInstallationReceipt,
)
from atlas.modules.connectors.domain.package_registration import ConnectorPackageRegistrationRecord


class ConnectorInstanceCreationError(RuntimeError):
    pass


class ConnectorInstanceInstallationSource(Protocol):
    async def connector_instance_creation_source(
        self, *, receipt_id: str
    ) -> tuple[
        ConnectorPackageInstallationReceipt,
        ConnectorPackageInstallationPolicySnapshot,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]: ...


class ConnectorInstanceCreationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorInstanceCreationPolicySnapshot | None: ...


class ConnectorInstanceRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, record_id: str) -> ConnectorInstanceRecord | None: ...

    async def get_by_scope_key(
        self, *, organization_id: str, environment_id: str, instance_key: str
    ) -> ConnectorInstanceRecord | None: ...

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> ConnectorInstanceRecord | None: ...

    async def add(self, record: ConnectorInstanceRecord) -> bool: ...

    async def close(self) -> None: ...
