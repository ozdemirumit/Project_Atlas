from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.deletion_legal_hold import (
    DeletionRequest,
    KnowledgeTombstone,
    LegalHold,
)


class InMemoryKnowledgeDeletionRepository:
    def __init__(self) -> None:
        self._holds: dict[str, LegalHold] = {}
        self._requests: dict[str, DeletionRequest] = {}
        self._tombstones: dict[str, KnowledgeTombstone] = {}
        self._lock = asyncio.Lock()

    async def save_hold(self, hold: LegalHold) -> None:
        async with self._lock:
            self._holds[hold.hold_id] = hold

    async def get_hold(self, hold_id: str) -> LegalHold | None:
        async with self._lock:
            return self._holds.get(hold_id)

    async def active_holds_for_item(self, item_id: str) -> tuple[LegalHold, ...]:
        async with self._lock:
            return tuple(
                hold
                for hold in self._holds.values()
                if hold.item_id == item_id and hold.released_at is None
            )

    async def save_request(self, request: DeletionRequest) -> None:
        async with self._lock:
            self._requests[request.request_id] = request

    async def get_request(self, request_id: str) -> DeletionRequest | None:
        async with self._lock:
            return self._requests.get(request_id)

    async def save_tombstone(self, tombstone: KnowledgeTombstone) -> None:
        async with self._lock:
            self._tombstones[tombstone.tombstone_id] = tombstone
