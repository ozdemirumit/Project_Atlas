from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.bounded_invocation import (
    ConnectorBoundedInvocationPolicySnapshot,
    ConnectorBoundedInvocationRecord,
    ConnectorInvocationConsumptionClaim,
)


class InMemoryConnectorBoundedInvocationRepository:
    def __init__(self) -> None:
        self._claims: dict[tuple[str, str, str], ConnectorInvocationConsumptionClaim] = {}
        self._claim_source_index: dict[tuple[str, str, str], str] = {}
        self._claim_idempotency_index: dict[tuple[str, str, str, str], str] = {}
        self._records: dict[tuple[str, str, str], ConnectorBoundedInvocationRecord] = {}
        self._record_source_index: dict[tuple[str, str, str], str] = {}
        self._record_claim_index: dict[tuple[str, str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get_in_scope(
        self, *, invocation_id: str, organization_id: str, environment_id: str
    ) -> ConnectorBoundedInvocationRecord | None:
        return self._records.get((organization_id, environment_id, invocation_id))

    async def get_by_authorization_in_scope(
        self,
        *,
        source_authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorBoundedInvocationRecord | None:
        invocation_id = self._record_source_index.get(
            (organization_id, environment_id, source_authorization_id)
        )
        return (
            self._records.get((organization_id, environment_id, invocation_id))
            if invocation_id
            else None
        )

    async def get_claim_by_authorization_in_scope(
        self,
        *,
        source_authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationConsumptionClaim | None:
        claim_id = self._claim_source_index.get(
            (organization_id, environment_id, source_authorization_id)
        )
        return self._claims.get((organization_id, environment_id, claim_id)) if claim_id else None

    async def get_claim_by_idempotency_in_scope(
        self,
        *,
        claimed_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationConsumptionClaim | None:
        claim_id = self._claim_idempotency_index.get(
            (organization_id, environment_id, claimed_by, idempotency_digest)
        )
        return self._claims.get((organization_id, environment_id, claim_id)) if claim_id else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorBoundedInvocationRecord, ...]:
        return tuple(
            record
            for (record_organization, record_environment, _), record in self._records.items()
            if record_organization == organization_id and record_environment == environment_id
        )

    async def claim(self, claim: ConnectorInvocationConsumptionClaim) -> bool:
        async with self._lock:
            scope = (claim.organization_id, claim.environment_id)
            claim_key = (*scope, claim.claim_id)
            source_key = (*scope, claim.source_authorization_id)
            idempotency_key = (*scope, claim.claimed_by, claim.idempotency_digest)
            if (
                claim_key in self._claims
                or source_key in self._claim_source_index
                or idempotency_key in self._claim_idempotency_index
            ):
                return False
            self._claims[claim_key] = claim
            self._claim_source_index[source_key] = claim.claim_id
            self._claim_idempotency_index[idempotency_key] = claim.claim_id
            return True

    async def add(self, record: ConnectorBoundedInvocationRecord) -> bool:
        async with self._lock:
            scope = (record.organization_id, record.environment_id)
            record_key = (*scope, record.invocation_id)
            source_key = (*scope, record.source_authorization_id)
            claim_key = (*scope, record.consumption_claim_id)
            if (
                record_key in self._records
                or source_key in self._record_source_index
                or claim_key in self._record_claim_index
                or claim_key not in self._claims
            ):
                return False
            self._records[record_key] = record
            self._record_source_index[source_key] = record.invocation_id
            self._record_claim_index[claim_key] = record.invocation_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorBoundedInvocationPolicySource:
    def __init__(self, policies: tuple[ConnectorBoundedInvocationPolicySnapshot, ...]) -> None:
        self._policies = {
            (item.organization_id, item.environment_id, item.policy_id): item for item in policies
        }

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorBoundedInvocationPolicySnapshot | None:
        return self._policies.get((organization_id, environment_id, policy_id))

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorBoundedInvocationPolicySnapshot, ...]:
        return tuple(
            policy
            for (policy_organization, policy_environment, _), policy in self._policies.items()
            if policy_organization == organization_id and policy_environment == environment_id
        )
