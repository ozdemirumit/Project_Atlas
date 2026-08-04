from __future__ import annotations

import asyncio

from atlas.modules.change_review.domain.packet import UpgradeChangeReviewPacket


class InMemoryChangeReviewPacketRepository:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], UpgradeChangeReviewPacket] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, actor_id: str, idempotency_key: str) -> UpgradeChangeReviewPacket | None:
        return self._records.get((actor_id, idempotency_key))

    async def add(self, record: UpgradeChangeReviewPacket) -> bool:
        async with self._lock:
            key = (record.actor_id, record.idempotency_key)
            if key in self._records:
                return False
            self._records[key] = record
            return True

    async def close(self) -> None:
        return None
