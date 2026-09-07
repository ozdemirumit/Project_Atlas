from __future__ import annotations

from typing import Protocol

from atlas.modules.guardrails.domain.human_review import (
    HumanReviewQueueEntry,
    HumanReviewResolution,
)


class GuardrailReviewRepository(Protocol):
    async def save_entry(self, entry: HumanReviewQueueEntry) -> None: ...

    async def get_entry(self, entry_id: str) -> HumanReviewQueueEntry | None: ...

    async def save_resolution(self, resolution: HumanReviewResolution) -> None: ...

    async def get_resolution(self, entry_id: str) -> HumanReviewResolution | None: ...
