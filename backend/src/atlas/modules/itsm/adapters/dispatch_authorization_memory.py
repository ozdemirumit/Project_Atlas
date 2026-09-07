from __future__ import annotations

import asyncio

from atlas.modules.itsm.application.dispatch_authorization_ports import (
    StoredItsmDispatchAuthorization,
)


class InMemoryItsmDispatchAuthorizationRepository:
    durable = False

    def __init__(self) -> None:
        self._records: dict[str, StoredItsmDispatchAuthorization] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, authorization_id: str) -> StoredItsmDispatchAuthorization | None:
        return self._records.get(authorization_id)

    async def get_by_idempotency_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> StoredItsmDispatchAuthorization | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.requested_by == requested_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, record: StoredItsmDispatchAuthorization) -> bool:
        async with self._lock:
            if record.authorization.authorization_id in self._records or any(
                item.requested_by == record.requested_by
                and item.idempotency_key == record.idempotency_key
                for item in self._records.values()
            ):
                return False
            self._records[record.authorization.authorization_id] = record
            return True

    async def close(self) -> None:
        return None
