from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.correction_resubmission import (
    OperationalKnowledgeCorrectionClaim,
    OperationalKnowledgeCorrectionPolicySnapshot,
    OperationalKnowledgeCorrectionRecord,
)


class InMemoryOperationalKnowledgeCorrectionPolicySource:
    def __init__(self, policies: tuple[OperationalKnowledgeCorrectionPolicySnapshot, ...]) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeCorrectionPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeCorrectionRepository:
    def __init__(self) -> None:
        self._claims: dict[str, OperationalKnowledgeCorrectionClaim] = {}
        self._claim_sources: dict[str, str] = {}
        self._claim_idempotency: dict[tuple[str, str], str] = {}
        self._records: dict[str, OperationalKnowledgeCorrectionRecord] = {}
        self._record_sources: dict[str, str] = {}
        self._record_new_requests: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, correction_id: str) -> OperationalKnowledgeCorrectionRecord | None:
        return self._records.get(correction_id)

    async def get_by_source_request(
        self, *, source_review_request_id: str
    ) -> OperationalKnowledgeCorrectionRecord | None:
        correction_id = self._record_sources.get(source_review_request_id)
        return self._records.get(correction_id) if correction_id else None

    async def get_claim_by_source_request(
        self, *, source_review_request_id: str
    ) -> OperationalKnowledgeCorrectionClaim | None:
        claim_id = self._claim_sources.get(source_review_request_id)
        return self._claims.get(claim_id) if claim_id else None

    async def get_by_new_review_request(
        self, *, new_review_request_id: str
    ) -> OperationalKnowledgeCorrectionRecord | None:
        correction_id = self._record_new_requests.get(new_review_request_id)
        return self._records.get(correction_id) if correction_id else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeCorrectionClaim | None:
        claim_id = self._claim_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return self._claims.get(claim_id) if claim_id else None

    async def claim(self, claim: OperationalKnowledgeCorrectionClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        async with self._lock:
            if (
                claim.claim_id in self._claims
                or claim.source_review_request_id in self._claim_sources
                or key in self._claim_idempotency
            ):
                return False
            self._claims[claim.claim_id] = claim
            self._claim_sources[claim.source_review_request_id] = claim.claim_id
            self._claim_idempotency[key] = claim.claim_id
            return True

    async def add(self, record: OperationalKnowledgeCorrectionRecord) -> bool:
        async with self._lock:
            if (
                record.correction_id in self._records
                or record.source_review_request_id in self._record_sources
                or record.new_review_request_id in self._record_new_requests
            ):
                return False
            self._records[record.correction_id] = record
            self._record_sources[record.source_review_request_id] = record.correction_id
            self._record_new_requests[record.new_review_request_id] = record.correction_id
            return True

    async def close(self) -> None:
        return None
