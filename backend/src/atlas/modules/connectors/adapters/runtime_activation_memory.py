from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
)
from atlas.modules.connectors.domain.runtime_activation import (
    ConnectorRuntimeActivationClaim,
    ConnectorRuntimeActivationPolicySnapshot,
    ConnectorRuntimeActivationProfileSnapshot,
    ConnectorRuntimeActivationRecord,
)


class InMemoryConnectorRuntimeActivationRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorRuntimeActivationRecord] = {}
        self._source_index: dict[tuple[str, str, str], str] = {}
        self._create_index: dict[tuple[str, str, str, str], str] = {}
        self._claims: dict[str, ConnectorRuntimeActivationClaim] = {}
        self._claim_source_index: dict[tuple[str, str, str], str] = {}
        self._claim_create_index: dict[tuple[str, str, str, str], str] = {}
        self._recovery_owners: dict[str, tuple[str, datetime]] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, activation_id: str) -> ConnectorRuntimeActivationRecord | None:
        return self._records.get(activation_id)

    async def get_in_scope(
        self,
        *,
        activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationRecord | None:
        record = self._records.get(activation_id)
        if (
            record is None
            or record.organization_id != organization_id
            or record.environment_id != environment_id
        ):
            return None
        return record

    async def get_by_brokerage_authorization(
        self, *, source_brokerage_authorization_id: str
    ) -> ConnectorRuntimeActivationRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.source_brokerage_authorization_id == source_brokerage_authorization_id
            ),
            None,
        )

    async def get_by_brokerage_authorization_in_scope(
        self,
        *,
        source_brokerage_authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationRecord | None:
        activation_id = self._source_index.get(
            (organization_id, environment_id, source_brokerage_authorization_id)
        )
        return self._records.get(activation_id) if activation_id else None

    async def get_by_create_key_in_scope(
        self,
        *,
        activated_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationRecord | None:
        idempotency_digest = ConnectorRuntimeActivationService._digest(
            [organization_id, environment_id, activated_by, idempotency_key]
        )
        activated_by_digest = ConnectorRuntimeActivationService._identifier_digest(activated_by)
        activation_id = self._create_index.get(
            (organization_id, environment_id, activated_by_digest, idempotency_digest)
        )
        return self._records.get(activation_id) if activation_id else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeActivationRecord, ...]:
        return tuple(
            sorted(
                (
                    record
                    for record in self._records.values()
                    if record.organization_id == organization_id
                    and record.environment_id == environment_id
                ),
                key=lambda record: record.activation_id,
            )
        )

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_brokerage_authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationClaim | None:
        attempt_id = self._claim_source_index.get(
            (organization_id, environment_id, source_brokerage_authorization_id)
        )
        return self._claims.get(attempt_id) if attempt_id else None

    async def add(self, record: ConnectorRuntimeActivationRecord) -> bool:
        async with self._lock:
            return self._add_unlocked(record, claim=None)

    async def claim(self, claim: ConnectorRuntimeActivationClaim) -> bool:
        async with self._lock:
            source_key = (
                claim.organization_id,
                claim.environment_id,
                claim.source_brokerage_authorization_id,
            )
            create_key = (
                claim.organization_id,
                claim.environment_id,
                claim.activated_by_digest,
                claim.idempotency_digest,
            )
            if (
                claim.activation_attempt_id in self._claims
                or source_key in self._source_index
                or source_key in self._claim_source_index
                or create_key in self._create_index
                or create_key in self._claim_create_index
            ):
                return False
            self._claims[claim.activation_attempt_id] = claim
            self._claim_source_index[source_key] = claim.activation_attempt_id
            self._claim_create_index[create_key] = claim.activation_attempt_id
            return True

    async def fence_expired_claim(
        self,
        *,
        claim: ConnectorRuntimeActivationClaim,
        recovery_attempt_id: str,
        now: datetime,
    ) -> bool:
        async with self._lock:
            if self._claims.get(claim.activation_attempt_id) != claim or claim.expires_at > now:
                return False
            recovery_owner = self._recovery_owners.get(claim.activation_attempt_id)
            if recovery_owner is not None and recovery_owner[1] > now:
                return False
            self._recovery_owners[claim.activation_attempt_id] = (
                recovery_attempt_id,
                now + timedelta(minutes=2),
            )
            return True

    async def release_claim(
        self,
        claim: ConnectorRuntimeActivationClaim,
        *,
        now: datetime,
        recovery_attempt_id: str | None = None,
    ) -> bool:
        async with self._lock:
            owner = self._recovery_owners.get(claim.activation_attempt_id)
            if (owner[0] if owner is not None else None) != recovery_attempt_id or (
                owner is not None and owner[1] <= now
            ):
                return False
            return self._release_claim_unlocked(claim)

    async def publish(
        self,
        *,
        claim: ConnectorRuntimeActivationClaim,
        record: ConnectorRuntimeActivationRecord,
        now: datetime,
    ) -> bool:
        async with self._lock:
            if (
                self._claims.get(claim.activation_attempt_id) != claim
                or claim.activation_attempt_id in self._recovery_owners
                or claim.expires_at <= now
            ):
                return False
            if not self._add_unlocked(record, claim=claim):
                return False
            self._release_claim_unlocked(claim)
            return True

    def _add_unlocked(
        self,
        record: ConnectorRuntimeActivationRecord,
        *,
        claim: ConnectorRuntimeActivationClaim | None,
    ) -> bool:
        source_key = (
            record.organization_id,
            record.environment_id,
            record.source_brokerage_authorization_id,
        )
        create_key = (
            record.organization_id,
            record.environment_id,
            ConnectorRuntimeActivationService._identifier_digest(record.activated_by),
            record.idempotency_digest,
        )
        pending_attempt = self._claim_source_index.get(source_key)
        pending_create_attempt = self._claim_create_index.get(create_key)
        if (
            record.activation_id in self._records
            or source_key in self._source_index
            or create_key in self._create_index
            or (
                pending_attempt is not None
                and (claim is None or pending_attempt != claim.activation_attempt_id)
            )
            or (
                pending_create_attempt is not None
                and (claim is None or pending_create_attempt != claim.activation_attempt_id)
            )
        ):
            return False
        self._records[record.activation_id] = record
        self._source_index[source_key] = record.activation_id
        self._create_index[create_key] = record.activation_id
        return True

    def _release_claim_unlocked(self, claim: ConnectorRuntimeActivationClaim) -> bool:
        if self._claims.get(claim.activation_attempt_id) != claim:
            return False
        del self._claims[claim.activation_attempt_id]
        self._recovery_owners.pop(claim.activation_attempt_id, None)
        self._claim_source_index.pop(
            (
                claim.organization_id,
                claim.environment_id,
                claim.source_brokerage_authorization_id,
            ),
            None,
        )
        self._claim_create_index.pop(
            (
                claim.organization_id,
                claim.environment_id,
                claim.activated_by_digest,
                claim.idempotency_digest,
            ),
            None,
        )
        return True

    async def close(self) -> None:
        return None


class InMemoryConnectorRuntimeActivationProfileSource:
    def __init__(self, profiles: tuple[ConnectorRuntimeActivationProfileSnapshot, ...]) -> None:
        self._profiles = {item.profile_id: item for item in profiles}

    async def get_by_id(
        self, *, profile_id: str
    ) -> ConnectorRuntimeActivationProfileSnapshot | None:
        return self._profiles.get(profile_id)

    async def get_by_id_in_scope(
        self,
        *,
        profile_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationProfileSnapshot | None:
        profile = self._profiles.get(profile_id)
        if (
            profile is None
            or profile.organization_id != organization_id
            or profile.environment_id != environment_id
        ):
            return None
        return profile

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeActivationProfileSnapshot, ...]:
        return tuple(
            sorted(
                (
                    profile
                    for profile in self._profiles.values()
                    if profile.organization_id == organization_id
                    and profile.environment_id == environment_id
                ),
                key=lambda profile: profile.profile_id,
            )
        )


class InMemoryConnectorRuntimeActivationPolicySource:
    def __init__(self, policies: tuple[ConnectorRuntimeActivationPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(self, *, policy_id: str) -> ConnectorRuntimeActivationPolicySnapshot | None:
        return self._policies.get(policy_id)

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationPolicySnapshot | None:
        policy = self._policies.get(policy_id)
        if (
            policy is None
            or policy.organization_id != organization_id
            or policy.environment_id != environment_id
        ):
            return None
        return policy

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeActivationPolicySnapshot, ...]:
        return tuple(
            sorted(
                (
                    policy
                    for policy in self._policies.values()
                    if policy.organization_id == organization_id
                    and policy.environment_id == environment_id
                ),
                key=lambda policy: policy.policy_id,
            )
        )
