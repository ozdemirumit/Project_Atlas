from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.runtime_trust import (
    ConnectorRuntimeTrustGrantRecord,
    ConnectorRuntimeTrustPolicySnapshot,
    ConnectorRuntimeTrustProfileSnapshot,
)


class InMemoryConnectorRuntimeTrustRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorRuntimeTrustGrantRecord] = {}
        self._enablement_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, grant_id: str) -> ConnectorRuntimeTrustGrantRecord | None:
        return self._records.get(grant_id)

    async def get_by_enablement(
        self, *, source_enablement_id: str
    ) -> ConnectorRuntimeTrustGrantRecord | None:
        grant_id = self._enablement_index.get(source_enablement_id)
        return self._records.get(grant_id) if grant_id else None

    async def get_by_create_key(
        self, *, granted_by: str, idempotency_key: str
    ) -> ConnectorRuntimeTrustGrantRecord | None:
        grant_id = self._create_index.get((granted_by, idempotency_key))
        return self._records.get(grant_id) if grant_id else None

    async def add(self, record: ConnectorRuntimeTrustGrantRecord) -> bool:
        async with self._lock:
            create_key = (record.granted_by, record.idempotency_key)
            if (
                record.grant_id in self._records
                or record.source_enablement_id in self._enablement_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.grant_id] = record
            self._enablement_index[record.source_enablement_id] = record.grant_id
            self._create_index[create_key] = record.grant_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorRuntimeTrustProfileSource:
    def __init__(self, profiles: tuple[ConnectorRuntimeTrustProfileSnapshot, ...]) -> None:
        self._profiles = {item.profile_id: item for item in profiles}

    async def get_by_id(self, *, profile_id: str) -> ConnectorRuntimeTrustProfileSnapshot | None:
        return self._profiles.get(profile_id)


class InMemoryConnectorRuntimeTrustPolicySource:
    def __init__(self, policies: tuple[ConnectorRuntimeTrustPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(self, *, policy_id: str) -> ConnectorRuntimeTrustPolicySnapshot | None:
        return self._policies.get(policy_id)
