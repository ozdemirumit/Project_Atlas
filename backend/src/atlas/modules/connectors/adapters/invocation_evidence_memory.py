from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.invocation_evidence import (
    ConnectorInvocationEvidenceClaim,
    ConnectorInvocationEvidencePolicySnapshot,
    ConnectorInvocationEvidenceRecord,
)


class InMemoryConnectorInvocationEvidencePolicySource:
    def __init__(self, policies: tuple[ConnectorInvocationEvidencePolicySnapshot, ...]) -> None:
        self._policies = {
            (item.organization_id, item.environment_id, item.policy_id): item for item in policies
        }

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationEvidencePolicySnapshot | None:
        return self._policies.get((organization_id, environment_id, policy_id))


class InMemoryConnectorInvocationEvidenceRepository:
    def __init__(self) -> None:
        self._claims: dict[tuple[str, str, str], ConnectorInvocationEvidenceClaim] = {}
        self._claims_by_invocation: dict[
            tuple[str, str, str], ConnectorInvocationEvidenceClaim
        ] = {}
        self._claims_by_idempotency: dict[
            tuple[str, str, str, str], ConnectorInvocationEvidenceClaim
        ] = {}
        self._records: dict[tuple[str, str, str], ConnectorInvocationEvidenceRecord] = {}
        self._records_by_invocation: dict[
            tuple[str, str, str], ConnectorInvocationEvidenceRecord
        ] = {}
        self._records_by_claim: dict[tuple[str, str, str], ConnectorInvocationEvidenceRecord] = {}
        self._lock = asyncio.Lock()

    async def get_in_scope(
        self, *, ingestion_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationEvidenceRecord | None:
        return self._records.get((organization_id, environment_id, ingestion_id))

    async def get_by_invocation_in_scope(
        self,
        *,
        source_invocation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationEvidenceRecord | None:
        return self._records_by_invocation.get(
            (organization_id, environment_id, source_invocation_id)
        )

    async def get_claim_by_invocation_in_scope(
        self,
        *,
        source_invocation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationEvidenceClaim | None:
        return self._claims_by_invocation.get(
            (organization_id, environment_id, source_invocation_id)
        )

    async def get_claim_by_idempotency_in_scope(
        self,
        *,
        claimed_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationEvidenceClaim | None:
        return self._claims_by_idempotency.get(
            (organization_id, environment_id, claimed_by, idempotency_digest)
        )

    async def claim(self, claim: ConnectorInvocationEvidenceClaim) -> bool:
        async with self._lock:
            claim_key = (
                claim.organization_id,
                claim.environment_id,
                claim.claim_id,
            )
            invocation_key = (
                claim.organization_id,
                claim.environment_id,
                claim.source_invocation_id,
            )
            idempotency_key = (
                claim.organization_id,
                claim.environment_id,
                claim.claimed_by,
                claim.idempotency_digest,
            )
            if (
                claim_key in self._claims
                or invocation_key in self._claims_by_invocation
                or idempotency_key in self._claims_by_idempotency
            ):
                return False
            self._claims[claim_key] = claim
            self._claims_by_invocation[invocation_key] = claim
            self._claims_by_idempotency[idempotency_key] = claim
            return True

    async def add(self, record: ConnectorInvocationEvidenceRecord) -> bool:
        async with self._lock:
            record_key = (
                record.organization_id,
                record.environment_id,
                record.ingestion_id,
            )
            invocation_key = (
                record.organization_id,
                record.environment_id,
                record.source_invocation_id,
            )
            claim_key = (
                record.organization_id,
                record.environment_id,
                record.claim_id,
            )
            claim = self._claims.get(claim_key)
            if (
                claim is None
                or claim.ingestion_id != record.ingestion_id
                or claim.source_invocation_id != record.source_invocation_id
                or record_key in self._records
                or invocation_key in self._records_by_invocation
                or claim_key in self._records_by_claim
            ):
                return False
            self._records[record_key] = record
            self._records_by_invocation[invocation_key] = record
            self._records_by_claim[claim_key] = record
            return True

    async def close(self) -> None:
        return None
