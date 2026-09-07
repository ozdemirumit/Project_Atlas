from __future__ import annotations

import asyncio

from atlas.modules.guardrails.domain.human_review import (
    HumanReviewQueueEntry,
    HumanReviewResolution,
)


class InMemoryGuardrailReviewRepository:
    def __init__(self) -> None:
        self._entries: dict[str, HumanReviewQueueEntry] = {}
        self._resolutions: dict[str, HumanReviewResolution] = {}
        self._lock = asyncio.Lock()

    async def save_entry(self, entry: HumanReviewQueueEntry) -> None:
        async with self._lock:
            self._entries[entry.entry_id] = entry

    async def get_entry(self, entry_id: str) -> HumanReviewQueueEntry | None:
        async with self._lock:
            return self._entries.get(entry_id)

    async def save_resolution(self, resolution: HumanReviewResolution) -> None:
        async with self._lock:
            self._resolutions[resolution.entry_id] = resolution

    async def get_resolution(self, entry_id: str) -> HumanReviewResolution | None:
        async with self._lock:
            return self._resolutions.get(entry_id)
