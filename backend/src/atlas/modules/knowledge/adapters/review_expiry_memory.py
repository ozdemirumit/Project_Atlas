from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.review_expiry import (
    OwnerAbsenceResolution,
    ReviewDueRecord,
    ReviewRenewal,
)


class InMemoryKnowledgeReviewRepository:
    def __init__(self) -> None:
        self._due: dict[str, ReviewDueRecord] = {}
        self._renewals: list[ReviewRenewal] = []
        self._owner_absence_resolutions: list[OwnerAbsenceResolution] = []
        self._lock = asyncio.Lock()

    async def get_due(self, item_id: str) -> ReviewDueRecord | None:
        async with self._lock:
            return self._due.get(item_id)

    async def save_due(self, record: ReviewDueRecord) -> None:
        async with self._lock:
            self._due[record.item_id] = record

    async def save_renewal(self, renewal: ReviewRenewal) -> None:
        async with self._lock:
            self._renewals.append(renewal)

    async def save_owner_absence_resolution(self, resolution: OwnerAbsenceResolution) -> None:
        async with self._lock:
            self._owner_absence_resolutions.append(resolution)
