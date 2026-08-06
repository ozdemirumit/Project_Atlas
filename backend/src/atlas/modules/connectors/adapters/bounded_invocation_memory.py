from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.bounded_invocation import (
    ConnectorBoundedInvocationPolicySnapshot,
    ConnectorBoundedInvocationRecord,
    ConnectorInvocationConsumptionClaim,
)


class InMemoryConnectorBoundedInvocationRepository:
    def __init__(self) -> None:
        self._claims: dict[str, ConnectorInvocationConsumptionClaim] = {}
        self._claim_source_index: dict[str, str] = {}
        self._claim_idempotency_index: dict[tuple[str, str], str] = {}
        self._records: dict[str, ConnectorBoundedInvocationRecord] = {}
        self._record_source_index: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, invocation_id: str) -> ConnectorBoundedInvocationRecord | None:
        return self._records.get(invocation_id)

    async def get_by_authorization(
        self, *, source_authorization_id: str
    ) -> ConnectorBoundedInvocationRecord | None:
        invocation_id = self._record_source_index.get(source_authorization_id)
        return self._records.get(invocation_id) if invocation_id else None

    async def get_claim_by_authorization(
        self, *, source_authorization_id: str
    ) -> ConnectorInvocationConsumptionClaim | None:
        claim_id = self._claim_source_index.get(source_authorization_id)
        return self._claims.get(claim_id) if claim_id else None

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> ConnectorInvocationConsumptionClaim | None:
        claim_id = self._claim_idempotency_index.get((claimed_by, idempotency_digest))
        return self._claims.get(claim_id) if claim_id else None

    async def claim(self, claim: ConnectorInvocationConsumptionClaim) -> bool:
        async with self._lock:
            key = (claim.claimed_by, claim.idempotency_digest)
            if (
                claim.claim_id in self._claims
                or claim.source_authorization_id in self._claim_source_index
                or key in self._claim_idempotency_index
            ):
                return False
            self._claims[claim.claim_id] = claim
            self._claim_source_index[claim.source_authorization_id] = claim.claim_id
            self._claim_idempotency_index[key] = claim.claim_id
            return True

    async def add(self, record: ConnectorBoundedInvocationRecord) -> bool:
        async with self._lock:
            if (
                record.invocation_id in self._records
                or record.source_authorization_id in self._record_source_index
                or record.consumption_claim_id not in self._claims
            ):
                return False
            self._records[record.invocation_id] = record
            self._record_source_index[record.source_authorization_id] = record.invocation_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorBoundedInvocationPolicySource:
    def __init__(self, policies: tuple[ConnectorBoundedInvocationPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(self, *, policy_id: str) -> ConnectorBoundedInvocationPolicySnapshot | None:
        return self._policies.get(policy_id)
