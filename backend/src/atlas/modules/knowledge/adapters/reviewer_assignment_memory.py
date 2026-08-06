from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentClaim,
    OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    OperationalKnowledgeReviewerAssignmentRecord,
)


class InMemoryOperationalKnowledgeReviewerAssignmentPolicySource:
    def __init__(
        self, policies: tuple[OperationalKnowledgeReviewerAssignmentPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeReviewerAssignmentPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeReviewerAssignmentRepository:
    def __init__(self) -> None:
        self._claims_by_source: dict[str, OperationalKnowledgeReviewerAssignmentClaim] = {}
        self._claims_by_idempotency: dict[
            tuple[str, str], OperationalKnowledgeReviewerAssignmentClaim
        ] = {}
        self._records: dict[str, OperationalKnowledgeReviewerAssignmentRecord] = {}
        self._record_ids_by_source: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, assignment_set_id: str
    ) -> OperationalKnowledgeReviewerAssignmentRecord | None:
        return self._records.get(assignment_set_id)

    async def get_by_source(
        self, *, source_review_request_id: str
    ) -> OperationalKnowledgeReviewerAssignmentRecord | None:
        record_id = self._record_ids_by_source.get(source_review_request_id)
        return self._records.get(record_id) if record_id is not None else None

    async def get_claim_by_source(
        self, *, source_review_request_id: str
    ) -> OperationalKnowledgeReviewerAssignmentClaim | None:
        return self._claims_by_source.get(source_review_request_id)

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> OperationalKnowledgeReviewerAssignmentClaim | None:
        return self._claims_by_idempotency.get((claimed_by, idempotency_digest))

    async def claim(self, claim: OperationalKnowledgeReviewerAssignmentClaim) -> bool:
        async with self._lock:
            idempotency_key = (claim.claimed_by, claim.idempotency_digest)
            if (
                claim.source_review_request_id in self._claims_by_source
                or idempotency_key in self._claims_by_idempotency
            ):
                return False
            self._claims_by_source[claim.source_review_request_id] = claim
            self._claims_by_idempotency[idempotency_key] = claim
            return True

    async def add(self, record: OperationalKnowledgeReviewerAssignmentRecord) -> bool:
        async with self._lock:
            if (
                record.assignment_set_id in self._records
                or record.source_review_request_id in self._record_ids_by_source
            ):
                return False
            self._records[record.assignment_set_id] = record
            self._record_ids_by_source[record.source_review_request_id] = record.assignment_set_id
            return True

    async def close(self) -> None:
        return None
