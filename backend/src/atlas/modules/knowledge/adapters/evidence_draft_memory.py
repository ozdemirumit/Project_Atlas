from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.evidence_draft import (
    OperationalEvidenceKnowledgeDraftClaim,
    OperationalEvidenceKnowledgeDraftPolicySnapshot,
    OperationalEvidenceKnowledgeDraftRecord,
)


class InMemoryOperationalEvidenceKnowledgeDraftPolicySource:
    def __init__(
        self, policies: tuple[OperationalEvidenceKnowledgeDraftPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalEvidenceKnowledgeDraftPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalEvidenceKnowledgeDraftRepository:
    def __init__(self) -> None:
        self._claims_by_source: dict[str, OperationalEvidenceKnowledgeDraftClaim] = {}
        self._claims_by_idempotency: dict[
            tuple[str, str], OperationalEvidenceKnowledgeDraftClaim
        ] = {}
        self._records: dict[str, OperationalEvidenceKnowledgeDraftRecord] = {}
        self._records_by_source: dict[str, OperationalEvidenceKnowledgeDraftRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, draft_id: str) -> OperationalEvidenceKnowledgeDraftRecord | None:
        return self._records.get(draft_id)

    async def get_by_source(
        self, *, source_ingestion_id: str
    ) -> OperationalEvidenceKnowledgeDraftRecord | None:
        return self._records_by_source.get(source_ingestion_id)

    async def get_claim_by_source(
        self, *, source_ingestion_id: str
    ) -> OperationalEvidenceKnowledgeDraftClaim | None:
        return self._claims_by_source.get(source_ingestion_id)

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> OperationalEvidenceKnowledgeDraftClaim | None:
        return self._claims_by_idempotency.get((claimed_by, idempotency_digest))

    async def claim(self, claim: OperationalEvidenceKnowledgeDraftClaim) -> bool:
        async with self._lock:
            key = (claim.claimed_by, claim.idempotency_digest)
            if (
                claim.source_ingestion_id in self._claims_by_source
                or key in self._claims_by_idempotency
            ):
                return False
            self._claims_by_source[claim.source_ingestion_id] = claim
            self._claims_by_idempotency[key] = claim
            return True

    async def add(self, record: OperationalEvidenceKnowledgeDraftRecord) -> bool:
        async with self._lock:
            if (
                record.draft_id in self._records
                or record.source_ingestion_id in self._records_by_source
            ):
                return False
            self._records[record.draft_id] = record
            self._records_by_source[record.source_ingestion_id] = record
            return True

    async def close(self) -> None:
        return None
