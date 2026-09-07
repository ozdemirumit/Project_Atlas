from __future__ import annotations

from typing import Protocol

from atlas.modules.knowledge.domain.deletion_legal_hold import (
    DeletionRequest,
    KnowledgeTombstone,
    LegalHold,
)


class KnowledgeDeletionRepository(Protocol):
    async def save_hold(self, hold: LegalHold) -> None: ...

    async def get_hold(self, hold_id: str) -> LegalHold | None: ...

    async def active_holds_for_item(self, item_id: str) -> tuple[LegalHold, ...]: ...

    async def save_request(self, request: DeletionRequest) -> None: ...

    async def get_request(self, request_id: str) -> DeletionRequest | None: ...

    async def save_tombstone(self, tombstone: KnowledgeTombstone) -> None: ...
