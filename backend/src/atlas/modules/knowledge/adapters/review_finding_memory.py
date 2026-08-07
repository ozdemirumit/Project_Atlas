from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.review_finding import (
    OperationalKnowledgeReviewFindingClaim,
    OperationalKnowledgeReviewFindingPolicySnapshot,
    OperationalKnowledgeReviewFindingRecord,
)


class InMemoryOperationalKnowledgeReviewFindingPolicySource:
    def __init__(
        self, policies: tuple[OperationalKnowledgeReviewFindingPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeReviewFindingPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeReviewFindingRepository:
    def __init__(self) -> None:
        self._claims_by_presentation: dict[str, OperationalKnowledgeReviewFindingClaim] = {}
        self._claims_by_idempotency: dict[
            tuple[str, str], OperationalKnowledgeReviewFindingClaim
        ] = {}
        self._records: dict[str, OperationalKnowledgeReviewFindingRecord] = {}
        self._record_ids_by_presentation: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, finding_packet_id: str
    ) -> OperationalKnowledgeReviewFindingRecord | None:
        return self._records.get(finding_packet_id)

    async def get_by_source_presentation(
        self, *, source_presentation_id: str
    ) -> OperationalKnowledgeReviewFindingRecord | None:
        record_id = self._record_ids_by_presentation.get(source_presentation_id)
        return self._records.get(record_id) if record_id is not None else None

    async def get_claim_by_source_presentation(
        self, *, source_presentation_id: str
    ) -> OperationalKnowledgeReviewFindingClaim | None:
        return self._claims_by_presentation.get(source_presentation_id)

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeReviewFindingClaim | None:
        return self._claims_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))

    async def claim(self, claim: OperationalKnowledgeReviewFindingClaim) -> bool:
        async with self._lock:
            idempotency_key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
            if (
                claim.source_presentation_id in self._claims_by_presentation
                or idempotency_key in self._claims_by_idempotency
            ):
                return False
            self._claims_by_presentation[claim.source_presentation_id] = claim
            self._claims_by_idempotency[idempotency_key] = claim
            return True

    async def add(self, record: OperationalKnowledgeReviewFindingRecord) -> bool:
        async with self._lock:
            if (
                record.finding_packet_id in self._records
                or record.source_presentation_id in self._record_ids_by_presentation
            ):
                return False
            self._records[record.finding_packet_id] = record
            self._record_ids_by_presentation[record.source_presentation_id] = (
                record.finding_packet_id
            )
            return True

    async def close(self) -> None:
        return None
