from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.publication_preparation import (
    OperationalKnowledgePublicationPreparationClaim,
    OperationalKnowledgePublicationPreparationPolicySnapshot,
    OperationalKnowledgePublicationPreparationRecord,
)


class InMemoryOperationalKnowledgePublicationPreparationPolicySource:
    def __init__(
        self, policies: tuple[OperationalKnowledgePublicationPreparationPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgePublicationPreparationPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgePublicationPreparationRepository:
    def __init__(self) -> None:
        self._claims: dict[str, OperationalKnowledgePublicationPreparationClaim] = {}
        self._claim_resolutions: dict[str, str] = {}
        self._claim_idempotency: dict[tuple[str, str], str] = {}
        self._records: dict[str, OperationalKnowledgePublicationPreparationRecord] = {}
        self._record_resolutions: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, preparation_id: str
    ) -> OperationalKnowledgePublicationPreparationRecord | None:
        return self._records.get(preparation_id)

    async def get_by_resolution(
        self, *, resolution_id: str
    ) -> OperationalKnowledgePublicationPreparationRecord | None:
        preparation_id = self._record_resolutions.get(resolution_id)
        return self._records.get(preparation_id) if preparation_id else None

    async def get_claim_by_resolution(
        self, *, resolution_id: str
    ) -> OperationalKnowledgePublicationPreparationClaim | None:
        claim_id = self._claim_resolutions.get(resolution_id)
        return self._claims.get(claim_id) if claim_id else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgePublicationPreparationClaim | None:
        claim_id = self._claim_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return self._claims.get(claim_id) if claim_id else None

    async def claim(self, claim: OperationalKnowledgePublicationPreparationClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        async with self._lock:
            if (
                claim.claim_id in self._claims
                or claim.resolution_id in self._claim_resolutions
                or key in self._claim_idempotency
            ):
                return False
            self._claims[claim.claim_id] = claim
            self._claim_resolutions[claim.resolution_id] = claim.claim_id
            self._claim_idempotency[key] = claim.claim_id
            return True

    async def add(self, record: OperationalKnowledgePublicationPreparationRecord) -> bool:
        async with self._lock:
            if (
                record.preparation_id in self._records
                or record.resolution_id in self._record_resolutions
            ):
                return False
            self._records[record.preparation_id] = record
            self._record_resolutions[record.resolution_id] = record.preparation_id
            return True

    async def close(self) -> None:
        return None
