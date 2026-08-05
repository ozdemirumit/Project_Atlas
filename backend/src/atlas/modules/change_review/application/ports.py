from __future__ import annotations

from typing import Protocol

from atlas.modules.change_review.domain.packet import UpgradeChangeReviewPacket


class ChangeReviewError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ChangeReviewPacketRepository(Protocol):
    @property
    def durable(self) -> bool: ...
    async def get(
        self, *, actor_id: str, idempotency_key: str
    ) -> UpgradeChangeReviewPacket | None: ...
    async def get_by_id(self, *, packet_id: str) -> UpgradeChangeReviewPacket | None: ...
    async def add(self, record: UpgradeChangeReviewPacket) -> bool: ...
    async def close(self) -> None: ...
