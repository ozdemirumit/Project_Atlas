from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionPolicySnapshot,
    ConnectorTargetSessionProfileSnapshot,
    ConnectorTargetSessionVerificationRecord,
)


class InMemoryConnectorTargetSessionRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorTargetSessionVerificationRecord] = {}
        self._source_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, verification_id: str) -> ConnectorTargetSessionVerificationRecord | None:
        return self._records.get(verification_id)

    async def get_by_runtime_activation(
        self, *, source_runtime_activation_id: str
    ) -> ConnectorTargetSessionVerificationRecord | None:
        verification_id = self._source_index.get(source_runtime_activation_id)
        return self._records.get(verification_id) if verification_id else None

    async def get_by_create_key(
        self, *, verified_by: str, idempotency_key: str
    ) -> ConnectorTargetSessionVerificationRecord | None:
        verification_id = self._create_index.get((verified_by, idempotency_key))
        return self._records.get(verification_id) if verification_id else None

    async def add(self, record: ConnectorTargetSessionVerificationRecord) -> bool:
        async with self._lock:
            create_key = (record.verified_by, record.idempotency_key)
            if (
                record.verification_id in self._records
                or record.source_runtime_activation_id in self._source_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.verification_id] = record
            self._source_index[record.source_runtime_activation_id] = record.verification_id
            self._create_index[create_key] = record.verification_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorTargetSessionProfileSource:
    def __init__(self, profiles: tuple[ConnectorTargetSessionProfileSnapshot, ...]) -> None:
        self._profiles = {item.profile_id: item for item in profiles}

    async def get_by_id(self, *, profile_id: str) -> ConnectorTargetSessionProfileSnapshot | None:
        return self._profiles.get(profile_id)


class InMemoryConnectorTargetSessionPolicySource:
    def __init__(self, policies: tuple[ConnectorTargetSessionPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(self, *, policy_id: str) -> ConnectorTargetSessionPolicySnapshot | None:
        return self._policies.get(policy_id)
