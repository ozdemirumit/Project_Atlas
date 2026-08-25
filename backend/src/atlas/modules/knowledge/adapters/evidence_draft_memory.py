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
        self._policies = {
            (policy.organization_id, policy.environment_id, policy.policy_id): policy
            for policy in policies
        }

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalEvidenceKnowledgeDraftPolicySnapshot | None:
        return self._policies.get((organization_id, environment_id, policy_id))

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[OperationalEvidenceKnowledgeDraftPolicySnapshot, ...]:
        return tuple(
            policy
            for (policy_organization, policy_environment, _), policy in self._policies.items()
            if policy_organization == organization_id and policy_environment == environment_id
        )


class InMemoryOperationalEvidenceKnowledgeDraftRepository:
    def __init__(self) -> None:
        self._claims: dict[tuple[str, str, str], OperationalEvidenceKnowledgeDraftClaim] = {}
        self._claims_by_source: dict[
            tuple[str, str, str], OperationalEvidenceKnowledgeDraftClaim
        ] = {}
        self._claims_by_idempotency: dict[
            tuple[str, str, str, str], OperationalEvidenceKnowledgeDraftClaim
        ] = {}
        self._records: dict[tuple[str, str, str], OperationalEvidenceKnowledgeDraftRecord] = {}
        self._records_by_source: dict[
            tuple[str, str, str], OperationalEvidenceKnowledgeDraftRecord
        ] = {}
        self._records_by_claim: dict[
            tuple[str, str, str], OperationalEvidenceKnowledgeDraftRecord
        ] = {}
        self._lock = asyncio.Lock()

    async def get_in_scope(
        self, *, draft_id: str, organization_id: str, environment_id: str
    ) -> OperationalEvidenceKnowledgeDraftRecord | None:
        return self._records.get((organization_id, environment_id, draft_id))

    async def get_by_source_in_scope(
        self,
        *,
        source_ingestion_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalEvidenceKnowledgeDraftRecord | None:
        return self._records_by_source.get((organization_id, environment_id, source_ingestion_id))

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_ingestion_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalEvidenceKnowledgeDraftClaim | None:
        return self._claims_by_source.get((organization_id, environment_id, source_ingestion_id))

    async def get_claim_by_idempotency_in_scope(
        self,
        *,
        claimed_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalEvidenceKnowledgeDraftClaim | None:
        return self._claims_by_idempotency.get(
            (organization_id, environment_id, claimed_by, idempotency_digest)
        )

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[OperationalEvidenceKnowledgeDraftRecord, ...]:
        return tuple(
            record
            for (record_organization, record_environment, _), record in self._records.items()
            if record_organization == organization_id and record_environment == environment_id
        )

    async def claim(self, claim: OperationalEvidenceKnowledgeDraftClaim) -> bool:
        async with self._lock:
            claim_key = (claim.organization_id, claim.environment_id, claim.claim_id)
            source_key = (
                claim.organization_id,
                claim.environment_id,
                claim.source_ingestion_id,
            )
            idempotency_key = (
                claim.organization_id,
                claim.environment_id,
                claim.claimed_by,
                claim.idempotency_digest,
            )
            if (
                claim_key in self._claims
                or source_key in self._claims_by_source
                or idempotency_key in self._claims_by_idempotency
            ):
                return False
            self._claims[claim_key] = claim
            self._claims_by_source[source_key] = claim
            self._claims_by_idempotency[idempotency_key] = claim
            return True

    async def add(self, record: OperationalEvidenceKnowledgeDraftRecord) -> bool:
        async with self._lock:
            record_key = (record.organization_id, record.environment_id, record.draft_id)
            source_key = (
                record.organization_id,
                record.environment_id,
                record.source_ingestion_id,
            )
            claim_key = (record.organization_id, record.environment_id, record.claim_id)
            claim = self._claims.get(claim_key)
            if (
                claim is None
                or claim.draft_id != record.draft_id
                or claim.source_ingestion_id != record.source_ingestion_id
                or record_key in self._records
                or source_key in self._records_by_source
                or claim_key in self._records_by_claim
            ):
                return False
            self._records[record_key] = record
            self._records_by_source[source_key] = record
            self._records_by_claim[claim_key] = record
            return True

    async def close(self) -> None:
        return None
