from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestClaim,
    OperationalKnowledgeReviewRequestPolicySnapshot,
    OperationalKnowledgeReviewRequestRecord,
)


class InMemoryOperationalKnowledgeReviewRequestPolicySource:
    def __init__(
        self, policies: tuple[OperationalKnowledgeReviewRequestPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeReviewRequestPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeReviewRequestRepository:
    def __init__(self) -> None:
        self._claims_by_source: dict[str, OperationalKnowledgeReviewRequestClaim] = {}
        self._claims_by_idempotency: dict[
            tuple[str, str], OperationalKnowledgeReviewRequestClaim
        ] = {}
        self._records: dict[str, OperationalKnowledgeReviewRequestRecord] = {}
        self._record_ids_by_source: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, review_request_id: str
    ) -> OperationalKnowledgeReviewRequestRecord | None:
        return self._records.get(review_request_id)

    async def get_by_source(
        self, *, source_draft_id: str
    ) -> OperationalKnowledgeReviewRequestRecord | None:
        record_id = self._record_ids_by_source.get(source_draft_id)
        return self._records.get(record_id) if record_id is not None else None

    async def get_claim_by_source(
        self, *, source_draft_id: str
    ) -> OperationalKnowledgeReviewRequestClaim | None:
        return self._claims_by_source.get(source_draft_id)

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> OperationalKnowledgeReviewRequestClaim | None:
        return self._claims_by_idempotency.get((claimed_by, idempotency_digest))

    async def claim(self, claim: OperationalKnowledgeReviewRequestClaim) -> bool:
        async with self._lock:
            idempotency_key = (claim.claimed_by, claim.idempotency_digest)
            if (
                claim.source_draft_id in self._claims_by_source
                or idempotency_key in self._claims_by_idempotency
            ):
                return False
            self._claims_by_source[claim.source_draft_id] = claim
            self._claims_by_idempotency[idempotency_key] = claim
            return True

    async def add(self, record: OperationalKnowledgeReviewRequestRecord) -> bool:
        async with self._lock:
            if (
                record.review_request_id in self._records
                or record.source_draft_id in self._record_ids_by_source
            ):
                return False
            self._records[record.review_request_id] = record
            self._record_ids_by_source[record.source_draft_id] = record.review_request_id
            return True

    async def close(self) -> None:
        return None
