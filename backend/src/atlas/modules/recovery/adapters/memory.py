from __future__ import annotations

import asyncio

from atlas.modules.recovery.domain.backup import BackupRecord, RestoreValidation


class InMemoryRecoveryRepository:
    def __init__(self) -> None:
        self._backups: dict[tuple[str, str], BackupRecord] = {}
        self._validations: dict[tuple[str, str], RestoreValidation] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_backup(self, *, actor_id: str, idempotency_key: str) -> BackupRecord | None:
        return self._backups.get((actor_id, idempotency_key))

    async def get_backup_by_id(self, *, actor_id: str, backup_id: str) -> BackupRecord | None:
        return next(
            (
                item
                for (owner, _), item in self._backups.items()
                if owner == actor_id and item.backup_id == backup_id
            ),
            None,
        )

    async def add_backup(self, record: BackupRecord) -> bool:
        async with self._lock:
            key = (record.actor_id, record.idempotency_key)
            if key in self._backups:
                return False
            self._backups[key] = record
            return True

    async def get_validation(
        self, *, actor_id: str, idempotency_key: str
    ) -> RestoreValidation | None:
        return self._validations.get((actor_id, idempotency_key))

    async def add_validation(self, record: RestoreValidation) -> bool:
        async with self._lock:
            key = (record.actor_id, record.idempotency_key)
            if key in self._validations:
                return False
            self._validations[key] = record
            return True

    async def close(self) -> None:
        return None
