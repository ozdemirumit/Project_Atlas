from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
    ConnectorSecretBrokeragePolicySnapshot,
    ConnectorSecretBrokerageProfileSnapshot,
)


class InMemoryConnectorSecretBrokerageRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorSecretBrokerageAuthorizationRecord] = {}
        self._source_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, authorization_id: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        return self._records.get(authorization_id)

    async def get_by_runtime_trust(
        self, *, source_runtime_trust_grant_id: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        authorization_id = self._source_index.get(source_runtime_trust_grant_id)
        return self._records.get(authorization_id) if authorization_id else None

    async def get_by_create_key(
        self, *, authorized_by: str, idempotency_key: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        authorization_id = self._create_index.get((authorized_by, idempotency_key))
        return self._records.get(authorization_id) if authorization_id else None

    async def add(self, record: ConnectorSecretBrokerageAuthorizationRecord) -> bool:
        async with self._lock:
            create_key = (record.authorized_by, record.idempotency_key)
            if (
                record.authorization_id in self._records
                or record.source_runtime_trust_grant_id in self._source_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.authorization_id] = record
            self._source_index[record.source_runtime_trust_grant_id] = record.authorization_id
            self._create_index[create_key] = record.authorization_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorSecretBrokerageProfileSource:
    def __init__(self, profiles: tuple[ConnectorSecretBrokerageProfileSnapshot, ...]) -> None:
        self._profiles = {item.profile_id: item for item in profiles}

    async def get_by_id(self, *, profile_id: str) -> ConnectorSecretBrokerageProfileSnapshot | None:
        return self._profiles.get(profile_id)


class InMemoryConnectorSecretBrokeragePolicySource:
    def __init__(self, policies: tuple[ConnectorSecretBrokeragePolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(self, *, policy_id: str) -> ConnectorSecretBrokeragePolicySnapshot | None:
        return self._policies.get(policy_id)
