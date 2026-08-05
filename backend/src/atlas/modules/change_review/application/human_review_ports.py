from __future__ import annotations

from typing import Protocol

from atlas.modules.change_review.domain.human_review import UpgradeChangeHumanReview


class HumanReviewRepository(Protocol):
    @property
    def durable(self) -> bool: ...
    async def get_by_id(self, *, review_id: str) -> UpgradeChangeHumanReview | None: ...
    async def get_by_create_key(
        self, *, requester_id: str, idempotency_key: str
    ) -> UpgradeChangeHumanReview | None: ...
    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        site_id: str,
        limit: int,
    ) -> tuple[UpgradeChangeHumanReview, ...]: ...
    async def add(self, record: UpgradeChangeHumanReview) -> bool: ...
    async def update(self, record: UpgradeChangeHumanReview, *, expected_version: int) -> bool: ...
    async def close(self) -> None: ...
