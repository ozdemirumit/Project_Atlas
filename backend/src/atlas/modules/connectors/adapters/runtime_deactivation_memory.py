from __future__ import annotations

import asyncio

from atlas.modules.connectors.application.runtime_deactivation import (
    ConnectorRuntimeDeactivationService,
)
from atlas.modules.connectors.domain.runtime_deactivation import (
    ConnectorRuntimeDeactivationRecord,
)


class InMemoryConnectorRuntimeDeactivationRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorRuntimeDeactivationRecord] = {}
        self._activation_index: dict[tuple[str, str, str], str] = {}
        self._create_index: dict[tuple[str, str, str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get_by_activation_in_scope(
        self,
        *,
        activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeDeactivationRecord | None:
        deactivation_id = self._activation_index.get(
            (organization_id, environment_id, activation_id)
        )
        return self._records.get(deactivation_id) if deactivation_id else None

    async def get_by_create_key_in_scope(
        self,
        *,
        deactivated_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeDeactivationRecord | None:
        actor_digest = ConnectorRuntimeDeactivationService._identifier_digest(deactivated_by)
        key_digest = ConnectorRuntimeDeactivationService._digest(
            [organization_id, environment_id, deactivated_by, idempotency_key]
        )
        deactivation_id = self._create_index.get(
            (organization_id, environment_id, actor_digest, key_digest)
        )
        return self._records.get(deactivation_id) if deactivation_id else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeDeactivationRecord, ...]:
        return tuple(
            sorted(
                (
                    record
                    for record in self._records.values()
                    if record.organization_id == organization_id
                    and record.environment_id == environment_id
                ),
                key=lambda record: record.deactivation_id,
            )
        )

    async def add(self, record: ConnectorRuntimeDeactivationRecord) -> bool:
        async with self._lock:
            activation_key = (
                record.organization_id,
                record.environment_id,
                record.activation_id,
            )
            create_key = (
                record.organization_id,
                record.environment_id,
                ConnectorRuntimeDeactivationService._identifier_digest(record.deactivated_by),
                record.idempotency_digest,
            )
            if (
                record.deactivation_id in self._records
                or activation_key in self._activation_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.deactivation_id] = record
            self._activation_index[activation_key] = record.deactivation_id
            self._create_index[create_key] = record.deactivation_id
            return True

    async def close(self) -> None:
        return None
