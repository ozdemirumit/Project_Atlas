from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.instance_creation import (
    ConnectorInstanceCreationPolicySnapshot,
    ConnectorInstanceRecord,
)
from atlas.modules.connectors.domain.package_installation import ConnectorPackageInstallationReceipt
from atlas.modules.connectors.domain.package_registration import ConnectorPackageRegistrationRecord
from atlas.modules.connectors.domain.target_configuration import (
    ConnectorTargetConfigurationBinding,
    ConnectorTargetConfigurationPolicySnapshot,
    ConnectorTargetProfileSnapshot,
)


class ConnectorTargetConfigurationError(RuntimeError):
    pass


class ConnectorTargetInstanceSource(Protocol):
    async def target_configuration_source(
        self, *, record_id: str
    ) -> tuple[
        ConnectorInstanceRecord,
        ConnectorInstanceCreationPolicySnapshot,
        ConnectorPackageInstallationReceipt,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]: ...


class ConnectorTargetProfileSource(Protocol):
    async def get_by_id(self, *, profile_id: str) -> ConnectorTargetProfileSnapshot | None: ...


class ConnectorTargetConfigurationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorTargetConfigurationPolicySnapshot | None: ...


class ConnectorTargetConfigurationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, binding_id: str) -> ConnectorTargetConfigurationBinding | None: ...

    async def get_by_instance(
        self, *, source_instance_record_id: str
    ) -> ConnectorTargetConfigurationBinding | None: ...

    async def get_by_create_key(
        self, *, bound_by: str, idempotency_key: str
    ) -> ConnectorTargetConfigurationBinding | None: ...

    async def add(self, binding: ConnectorTargetConfigurationBinding) -> bool: ...

    async def close(self) -> None: ...
