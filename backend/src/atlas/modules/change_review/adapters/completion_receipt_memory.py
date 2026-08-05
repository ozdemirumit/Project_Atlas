from __future__ import annotations

import asyncio

from atlas.modules.change_review.domain.completion_receipt import HumanReviewCompletionReceipt


class InMemoryCompletionReceiptRepository:
    def __init__(self) -> None:
        self._records: dict[str, HumanReviewCompletionReceipt] = {}
        self._review_ids: dict[str, str] = {}
        self._create_keys: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, receipt_id: str) -> HumanReviewCompletionReceipt | None:
        return self._records.get(receipt_id)

    async def get_by_review_id(self, *, review_id: str) -> HumanReviewCompletionReceipt | None:
        receipt_id = self._review_ids.get(review_id)
        return self._records.get(receipt_id) if receipt_id is not None else None

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> HumanReviewCompletionReceipt | None:
        receipt_id = self._create_keys.get((created_by, idempotency_key))
        return self._records.get(receipt_id) if receipt_id is not None else None

    async def add(self, record: HumanReviewCompletionReceipt) -> bool:
        async with self._lock:
            key = (record.created_by, record.idempotency_key)
            if (
                record.receipt_id in self._records
                or record.review_id in self._review_ids
                or key in self._create_keys
            ):
                return False
            self._records[record.receipt_id] = record
            self._review_ids[record.review_id] = record.receipt_id
            self._create_keys[key] = record.receipt_id
            return True

    async def close(self) -> None:
        return None
