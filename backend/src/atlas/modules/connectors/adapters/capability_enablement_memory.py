from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementPolicySnapshot,
    ConnectorCapabilityEnablementRecord,
    ConnectorCapabilityProfileSnapshot,
)


class InMemoryConnectorCapabilityEnablementRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorCapabilityEnablementRecord] = {}
        self._validation_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, enablement_id: str) -> ConnectorCapabilityEnablementRecord | None:
        return self._records.get(enablement_id)

    async def get_by_validation(
        self, *, source_validation_id: str
    ) -> ConnectorCapabilityEnablementRecord | None:
        enablement_id = self._validation_index.get(source_validation_id)
        return self._records.get(enablement_id) if enablement_id else None

    async def get_by_create_key(
        self, *, enabled_by: str, idempotency_key: str
    ) -> ConnectorCapabilityEnablementRecord | None:
        enablement_id = self._create_index.get((enabled_by, idempotency_key))
        return self._records.get(enablement_id) if enablement_id else None

    async def add(self, record: ConnectorCapabilityEnablementRecord) -> bool:
        async with self._lock:
            create_key = (record.enabled_by, record.idempotency_key)
            if (
                record.enablement_id in self._records
                or record.source_validation_id in self._validation_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.enablement_id] = record
            self._validation_index[record.source_validation_id] = record.enablement_id
            self._create_index[create_key] = record.enablement_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorCapabilityProfileSource:
    def __init__(self, profiles: tuple[ConnectorCapabilityProfileSnapshot, ...]) -> None:
        self._profiles = {item.profile_id: item for item in profiles}

    async def get_by_id(self, *, profile_id: str) -> ConnectorCapabilityProfileSnapshot | None:
        return self._profiles.get(profile_id)


class InMemoryConnectorCapabilityEnablementPolicySource:
    def __init__(self, policies: tuple[ConnectorCapabilityEnablementPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorCapabilityEnablementPolicySnapshot | None:
        return self._policies.get(policy_id)
