from __future__ import annotations

import asyncio

from atlas.modules.reports.domain.handoff_review import ItsmHandoffHumanReview


class InMemoryItsmHandoffReviewRepository:
    def __init__(self) -> None:
        self._records: dict[str, ItsmHandoffHumanReview] = {}
        self._handoffs: dict[str, str] = {}
        self._create_keys: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, review_id: str) -> ItsmHandoffHumanReview | None:
        return self._records.get(review_id)

    async def get_by_handoff(self, *, handoff_draft_id: str) -> ItsmHandoffHumanReview | None:
        review_id = self._handoffs.get(handoff_draft_id)
        return self._records.get(review_id) if review_id else None

    async def get_by_create_key(
        self, *, reviewer_id: str, idempotency_key: str
    ) -> ItsmHandoffHumanReview | None:
        review_id = self._create_keys.get((reviewer_id, idempotency_key))
        return self._records.get(review_id) if review_id else None

    async def add(self, review: ItsmHandoffHumanReview) -> bool:
        async with self._lock:
            create_key = (review.reviewer_id, review.idempotency_key)
            if (
                review.review_id in self._records
                or review.handoff_draft_id in self._handoffs
                or create_key in self._create_keys
            ):
                return False
            self._records[review.review_id] = review
            self._handoffs[review.handoff_draft_id] = review.review_id
            self._create_keys[create_key] = review.review_id
            return True

    async def close(self) -> None:
        return None
