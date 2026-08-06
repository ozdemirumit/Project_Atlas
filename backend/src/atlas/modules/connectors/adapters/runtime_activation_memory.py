from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.runtime_activation import (
    ConnectorRuntimeActivationPolicySnapshot,
    ConnectorRuntimeActivationProfileSnapshot,
    ConnectorRuntimeActivationRecord,
)


class InMemoryConnectorRuntimeActivationRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorRuntimeActivationRecord] = {}
        self._source_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, activation_id: str) -> ConnectorRuntimeActivationRecord | None:
        return self._records.get(activation_id)

    async def get_by_brokerage_authorization(
        self, *, source_brokerage_authorization_id: str
    ) -> ConnectorRuntimeActivationRecord | None:
        activation_id = self._source_index.get(source_brokerage_authorization_id)
        return self._records.get(activation_id) if activation_id else None

    async def get_by_create_key(
        self, *, activated_by: str, idempotency_key: str
    ) -> ConnectorRuntimeActivationRecord | None:
        activation_id = self._create_index.get((activated_by, idempotency_key))
        return self._records.get(activation_id) if activation_id else None

    async def add(self, record: ConnectorRuntimeActivationRecord) -> bool:
        async with self._lock:
            create_key = (record.activated_by, record.idempotency_key)
            if (
                record.activation_id in self._records
                or record.source_brokerage_authorization_id in self._source_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.activation_id] = record
            self._source_index[record.source_brokerage_authorization_id] = record.activation_id
            self._create_index[create_key] = record.activation_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorRuntimeActivationProfileSource:
    def __init__(self, profiles: tuple[ConnectorRuntimeActivationProfileSnapshot, ...]) -> None:
        self._profiles = {item.profile_id: item for item in profiles}

    async def get_by_id(
        self, *, profile_id: str
    ) -> ConnectorRuntimeActivationProfileSnapshot | None:
        return self._profiles.get(profile_id)


class InMemoryConnectorRuntimeActivationPolicySource:
    def __init__(self, policies: tuple[ConnectorRuntimeActivationPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(self, *, policy_id: str) -> ConnectorRuntimeActivationPolicySnapshot | None:
        return self._policies.get(policy_id)
