from __future__ import annotations

import asyncio

from atlas.modules.change_review.domain.human_review import (
    HumanReviewState,
    UpgradeChangeHumanReview,
)


class InMemoryHumanReviewRepository:
    def __init__(self) -> None:
        self._records: dict[str, UpgradeChangeHumanReview] = {}
        self._create_keys: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, review_id: str) -> UpgradeChangeHumanReview | None:
        return self._records.get(review_id)

    async def get_by_create_key(
        self, *, requester_id: str, idempotency_key: str
    ) -> UpgradeChangeHumanReview | None:
        review_id = self._create_keys.get((requester_id, idempotency_key))
        return self._records.get(review_id) if review_id is not None else None

    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        site_id: str,
        limit: int,
    ) -> tuple[UpgradeChangeHumanReview, ...]:
        records = sorted(
            (
                record
                for record in self._records.values()
                if record.organization_id == organization_id
                and record.environment_id == environment_id
                and record.site_id == site_id
                and record.state is HumanReviewState.PENDING
            ),
            key=lambda record: (record.expires_at, record.review_id),
        )
        return tuple(records[:limit])

    async def add(self, record: UpgradeChangeHumanReview) -> bool:
        async with self._lock:
            key = (record.requester_id, record.idempotency_key)
            if record.review_id in self._records or key in self._create_keys:
                return False
            self._records[record.review_id] = record
            self._create_keys[key] = record.review_id
            return True

    async def update(self, record: UpgradeChangeHumanReview, *, expected_version: int) -> bool:
        async with self._lock:
            current = self._records.get(record.review_id)
            if current is None or current.version != expected_version:
                return False
            self._records[record.review_id] = record
            return True

    async def close(self) -> None:
        return None
