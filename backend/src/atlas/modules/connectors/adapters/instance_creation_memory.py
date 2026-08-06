from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.instance_creation import (
    ConnectorInstanceCreationPolicySnapshot,
    ConnectorInstanceRecord,
)


class InMemoryConnectorInstanceRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorInstanceRecord] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, record_id: str) -> ConnectorInstanceRecord | None:
        return self._records.get(record_id)

    async def get_by_scope_key(
        self, *, organization_id: str, environment_id: str, instance_key: str
    ) -> ConnectorInstanceRecord | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.organization_id == organization_id
                and item.environment_id == environment_id
                and item.instance_key == instance_key
            ),
            None,
        )

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> ConnectorInstanceRecord | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.created_by == created_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, record: ConnectorInstanceRecord) -> bool:
        async with self._lock:
            if record.record_id in self._records:
                return False
            if any(
                (
                    item.organization_id == record.organization_id
                    and item.environment_id == record.environment_id
                    and item.instance_key == record.instance_key
                )
                or (
                    item.created_by == record.created_by
                    and item.idempotency_key == record.idempotency_key
                )
                for item in self._records.values()
            ):
                return False
            self._records[record.record_id] = record
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorInstanceCreationPolicySource:
    def __init__(self, policies: tuple[ConnectorInstanceCreationPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(self, *, policy_id: str) -> ConnectorInstanceCreationPolicySnapshot | None:
        return self._policies.get(policy_id)
