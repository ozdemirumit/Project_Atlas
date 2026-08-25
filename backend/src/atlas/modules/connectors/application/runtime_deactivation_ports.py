from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.runtime_activation import ConnectorRuntimeActivationRecord
from atlas.modules.connectors.domain.runtime_deactivation import (
    ConnectorRuntimeDeactivationRecord,
)


class ConnectorRuntimeDeactivationError(RuntimeError):
    pass


class ConnectorRuntimeDeactivationActivationSource(Protocol):
    async def get_activation_for_deactivation(
        self,
        *,
        activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationRecord | None: ...


class ConnectorRuntimeDeactivationRepository(Protocol):
    async def get_by_activation_in_scope(
        self,
        *,
        activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeDeactivationRecord | None: ...

    async def get_by_create_key_in_scope(
        self,
        *,
        deactivated_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeDeactivationRecord | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeDeactivationRecord, ...]: ...

    async def add(self, record: ConnectorRuntimeDeactivationRecord) -> bool: ...

    async def close(self) -> None: ...
