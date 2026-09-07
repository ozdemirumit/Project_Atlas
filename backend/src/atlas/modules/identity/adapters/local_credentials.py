from __future__ import annotations

import asyncio

from atlas.modules.identity.domain.local_credentials import (
    LocalCredentialRecord,
    LocalRecoveryActivation,
)


class InMemoryLocalCredentialRepository:
    def __init__(self) -> None:
        self._records: dict[str, LocalCredentialRecord] = {}
        self._activations: dict[str, LocalRecoveryActivation] = {}
        self._lock = asyncio.Lock()

    async def get(self, subject_id: str) -> LocalCredentialRecord | None:
        async with self._lock:
            return self._records.get(subject_id)

    async def create(self, record: LocalCredentialRecord) -> bool:
        async with self._lock:
            if record.subject_id in self._records:
                return False
            self._records[record.subject_id] = record
            return True

    async def update(self, record: LocalCredentialRecord, *, expected_version: int) -> bool:
        async with self._lock:
            current = self._records.get(record.subject_id)
            if current is None or current.version != expected_version:
                return False
            self._records[record.subject_id] = record
            return True

    async def get_recovery_activation(self, subject_id: str) -> LocalRecoveryActivation | None:
        async with self._lock:
            return self._activations.get(subject_id)

    async def save_recovery_activation(self, activation: LocalRecoveryActivation) -> None:
        async with self._lock:
            self._activations[activation.subject_id] = activation
