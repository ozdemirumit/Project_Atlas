from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.credential_assignment import (
    ConnectorCredentialAssignmentPolicySnapshot,
    ConnectorCredentialAssignmentRecord,
    ConnectorCredentialProfileSnapshot,
)


class InMemoryConnectorCredentialAssignmentRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorCredentialAssignmentRecord] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, assignment_id: str) -> ConnectorCredentialAssignmentRecord | None:
        return self._records.get(assignment_id)

    async def get_by_target_binding(
        self, *, source_target_binding_id: str
    ) -> ConnectorCredentialAssignmentRecord | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.source_target_binding_id == source_target_binding_id
            ),
            None,
        )

    async def get_by_create_key(
        self, *, assigned_by: str, idempotency_key: str
    ) -> ConnectorCredentialAssignmentRecord | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.assigned_by == assigned_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, record: ConnectorCredentialAssignmentRecord) -> bool:
        async with self._lock:
            if record.assignment_id in self._records:
                return False
            if any(
                item.source_target_binding_id == record.source_target_binding_id
                or (
                    item.assigned_by == record.assigned_by
                    and item.idempotency_key == record.idempotency_key
                )
                for item in self._records.values()
            ):
                return False
            self._records[record.assignment_id] = record
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorCredentialProfileSource:
    def __init__(self, profiles: tuple[ConnectorCredentialProfileSnapshot, ...]) -> None:
        self._profiles = {item.profile_id: item for item in profiles}

    async def get_by_id(self, *, profile_id: str) -> ConnectorCredentialProfileSnapshot | None:
        return self._profiles.get(profile_id)


class InMemoryConnectorCredentialAssignmentPolicySource:
    def __init__(self, policies: tuple[ConnectorCredentialAssignmentPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorCredentialAssignmentPolicySnapshot | None:
        return self._policies.get(policy_id)
