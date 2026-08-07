from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.retrieval_index_publication import (
    OperationalKnowledgeRetrievalPublicationClaim,
    OperationalKnowledgeRetrievalPublicationPolicySnapshot,
    OperationalKnowledgeRetrievalPublicationRecord,
)


class InMemoryOperationalKnowledgeRetrievalPublicationPolicySource:
    def __init__(
        self, policies: tuple[OperationalKnowledgeRetrievalPublicationPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeRetrievalPublicationPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeRetrievalPublicationRepository:
    def __init__(self) -> None:
        self._claims: dict[str, OperationalKnowledgeRetrievalPublicationClaim] = {}
        self._claim_stagings: dict[str, str] = {}
        self._claim_idempotency: dict[tuple[str, str], str] = {}
        self._records: dict[str, OperationalKnowledgeRetrievalPublicationRecord] = {}
        self._record_stagings: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, publication_id: str
    ) -> OperationalKnowledgeRetrievalPublicationRecord | None:
        return self._records.get(publication_id)

    async def get_claim_by_index_staging(
        self, *, index_staging_id: str
    ) -> OperationalKnowledgeRetrievalPublicationClaim | None:
        claim_id = self._claim_stagings.get(index_staging_id)
        return self._claims.get(claim_id) if claim_id else None

    async def claim(self, claim: OperationalKnowledgeRetrievalPublicationClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        async with self._lock:
            if (
                claim.claim_id in self._claims
                or claim.index_staging_id in self._claim_stagings
                or key in self._claim_idempotency
            ):
                return False
            self._claims[claim.claim_id] = claim
            self._claim_stagings[claim.index_staging_id] = claim.claim_id
            self._claim_idempotency[key] = claim.claim_id
            return True

    async def add(self, record: OperationalKnowledgeRetrievalPublicationRecord) -> bool:
        async with self._lock:
            if (
                record.publication_id in self._records
                or record.index_staging_id in self._record_stagings
            ):
                return False
            self._records[record.publication_id] = record
            self._record_stagings[record.index_staging_id] = record.publication_id
            return True

    async def close(self) -> None:
        return None
