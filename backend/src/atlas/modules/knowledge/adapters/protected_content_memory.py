from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentClaim,
    OperationalKnowledgeProtectedContentPolicySnapshot,
    OperationalKnowledgeProtectedContentRecord,
)


class InMemoryOperationalKnowledgeProtectedContentPolicySource:
    def __init__(
        self, policies: tuple[OperationalKnowledgeProtectedContentPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeProtectedContentPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeProtectedContentRepository:
    def __init__(self) -> None:
        self._claims_by_lease: dict[str, OperationalKnowledgeProtectedContentClaim] = {}
        self._claims_by_idempotency: dict[
            tuple[str, str], OperationalKnowledgeProtectedContentClaim
        ] = {}
        self._records: dict[str, OperationalKnowledgeProtectedContentRecord] = {}
        self._record_ids_by_lease: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, presentation_id: str
    ) -> OperationalKnowledgeProtectedContentRecord | None:
        return self._records.get(presentation_id)

    async def get_by_source_lease(
        self, *, source_lease_id: str
    ) -> OperationalKnowledgeProtectedContentRecord | None:
        record_id = self._record_ids_by_lease.get(source_lease_id)
        return self._records.get(record_id) if record_id is not None else None

    async def get_claim_by_source_lease(
        self, *, source_lease_id: str
    ) -> OperationalKnowledgeProtectedContentClaim | None:
        return self._claims_by_lease.get(source_lease_id)

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeProtectedContentClaim | None:
        return self._claims_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))

    async def claim(self, claim: OperationalKnowledgeProtectedContentClaim) -> bool:
        async with self._lock:
            idempotency_key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
            if (
                claim.source_lease_id in self._claims_by_lease
                or idempotency_key in self._claims_by_idempotency
            ):
                return False
            self._claims_by_lease[claim.source_lease_id] = claim
            self._claims_by_idempotency[idempotency_key] = claim
            return True

    async def add(self, record: OperationalKnowledgeProtectedContentRecord) -> bool:
        async with self._lock:
            if (
                record.presentation_id in self._records
                or record.source_lease_id in self._record_ids_by_lease
            ):
                return False
            self._records[record.presentation_id] = record
            self._record_ids_by_lease[record.source_lease_id] = record.presentation_id
            return True

    async def close(self) -> None:
        return None
