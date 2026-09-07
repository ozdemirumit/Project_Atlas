from __future__ import annotations

from typing import Protocol

from atlas.modules.knowledge.domain.review_expiry import (
    OwnerAbsenceResolution,
    ReviewDueRecord,
    ReviewRenewal,
)


class KnowledgeReviewRepository(Protocol):
    async def get_due(self, item_id: str) -> ReviewDueRecord | None: ...

    async def save_due(self, record: ReviewDueRecord) -> None: ...

    async def save_renewal(self, renewal: ReviewRenewal) -> None: ...

    async def save_owner_absence_resolution(self, resolution: OwnerAbsenceResolution) -> None: ...
