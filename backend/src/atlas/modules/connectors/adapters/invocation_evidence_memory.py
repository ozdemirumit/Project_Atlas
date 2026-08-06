from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.invocation_evidence import (
    ConnectorInvocationEvidenceClaim,
    ConnectorInvocationEvidencePolicySnapshot,
    ConnectorInvocationEvidenceRecord,
)


class InMemoryConnectorInvocationEvidencePolicySource:
    def __init__(self, policies: tuple[ConnectorInvocationEvidencePolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorInvocationEvidencePolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryConnectorInvocationEvidenceRepository:
    def __init__(self) -> None:
        self._claims_by_invocation: dict[str, ConnectorInvocationEvidenceClaim] = {}
        self._claims_by_idempotency: dict[tuple[str, str], ConnectorInvocationEvidenceClaim] = {}
        self._records: dict[str, ConnectorInvocationEvidenceRecord] = {}
        self._records_by_invocation: dict[str, ConnectorInvocationEvidenceRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, ingestion_id: str) -> ConnectorInvocationEvidenceRecord | None:
        return self._records.get(ingestion_id)

    async def get_by_invocation(
        self, *, source_invocation_id: str
    ) -> ConnectorInvocationEvidenceRecord | None:
        return self._records_by_invocation.get(source_invocation_id)

    async def get_claim_by_invocation(
        self, *, source_invocation_id: str
    ) -> ConnectorInvocationEvidenceClaim | None:
        return self._claims_by_invocation.get(source_invocation_id)

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> ConnectorInvocationEvidenceClaim | None:
        return self._claims_by_idempotency.get((claimed_by, idempotency_digest))

    async def claim(self, claim: ConnectorInvocationEvidenceClaim) -> bool:
        async with self._lock:
            key = (claim.claimed_by, claim.idempotency_digest)
            if (
                claim.source_invocation_id in self._claims_by_invocation
                or key in self._claims_by_idempotency
            ):
                return False
            self._claims_by_invocation[claim.source_invocation_id] = claim
            self._claims_by_idempotency[key] = claim
            return True

    async def add(self, record: ConnectorInvocationEvidenceRecord) -> bool:
        async with self._lock:
            if (
                record.ingestion_id in self._records
                or record.source_invocation_id in self._records_by_invocation
            ):
                return False
            self._records[record.ingestion_id] = record
            self._records_by_invocation[record.source_invocation_id] = record
            return True

    async def close(self) -> None:
        return None
