from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from atlas.modules.connectors.application.target_session import ConnectorTargetSessionService
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionClaim,
    ConnectorTargetSessionPolicySnapshot,
    ConnectorTargetSessionProfileSnapshot,
    ConnectorTargetSessionVerificationRecord,
)


class InMemoryConnectorTargetSessionRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorTargetSessionVerificationRecord] = {}
        self._source_index: dict[tuple[str, str, str], str] = {}
        self._create_index: dict[tuple[str, str, str, str], str] = {}
        self._claims: dict[str, ConnectorTargetSessionClaim] = {}
        self._claim_source_index: dict[tuple[str, str, str], str] = {}
        self._claim_create_index: dict[tuple[str, str, str, str], str] = {}
        self._recovery_owners: dict[str, tuple[str, datetime]] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, verification_id: str) -> ConnectorTargetSessionVerificationRecord | None:
        return self._records.get(verification_id)

    async def get_in_scope(
        self,
        *,
        verification_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionVerificationRecord | None:
        record = self._records.get(verification_id)
        if (
            record is None
            or record.organization_id != organization_id
            or record.environment_id != environment_id
        ):
            return None
        return record

    async def get_by_runtime_activation(
        self, *, source_runtime_activation_id: str
    ) -> ConnectorTargetSessionVerificationRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.source_runtime_activation_id == source_runtime_activation_id
            ),
            None,
        )

    async def get_by_runtime_activation_in_scope(
        self,
        *,
        source_runtime_activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionVerificationRecord | None:
        verification_id = self._source_index.get(
            (organization_id, environment_id, source_runtime_activation_id)
        )
        return self._records.get(verification_id) if verification_id else None

    async def get_by_create_key(
        self, *, verified_by: str, idempotency_key: str
    ) -> ConnectorTargetSessionVerificationRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.verified_by == verified_by
                and record.idempotency_digest
                == ConnectorTargetSessionService._digest(
                    [
                        record.organization_id,
                        record.environment_id,
                        verified_by,
                        idempotency_key,
                    ]
                )
            ),
            None,
        )

    async def get_by_create_key_in_scope(
        self,
        *,
        verified_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionVerificationRecord | None:
        idempotency_digest = ConnectorTargetSessionService._digest(
            [organization_id, environment_id, verified_by, idempotency_key]
        )
        verified_by_digest = ConnectorTargetSessionService._identifier_digest(verified_by)
        verification_id = self._create_index.get(
            (organization_id, environment_id, verified_by_digest, idempotency_digest)
        )
        return self._records.get(verification_id) if verification_id else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorTargetSessionVerificationRecord, ...]:
        return tuple(
            sorted(
                (
                    record
                    for record in self._records.values()
                    if record.organization_id == organization_id
                    and record.environment_id == environment_id
                ),
                key=lambda record: record.verification_id,
            )
        )

    async def add(self, record: ConnectorTargetSessionVerificationRecord) -> bool:
        async with self._lock:
            return self._add_unlocked(record, claim=None)

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_runtime_activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionClaim | None:
        attempt_id = self._claim_source_index.get(
            (organization_id, environment_id, source_runtime_activation_id)
        )
        return self._claims.get(attempt_id) if attempt_id else None

    async def claim(self, claim: ConnectorTargetSessionClaim) -> bool:
        async with self._lock:
            source_key = (
                claim.organization_id,
                claim.environment_id,
                claim.source_runtime_activation_id,
            )
            create_key = (
                claim.organization_id,
                claim.environment_id,
                claim.verified_by_digest,
                claim.idempotency_digest,
            )
            if (
                claim.verification_attempt_id in self._claims
                or source_key in self._source_index
                or source_key in self._claim_source_index
                or create_key in self._create_index
                or create_key in self._claim_create_index
            ):
                return False
            self._claims[claim.verification_attempt_id] = claim
            self._claim_source_index[source_key] = claim.verification_attempt_id
            self._claim_create_index[create_key] = claim.verification_attempt_id
            return True

    async def fence_expired_claim(
        self,
        *,
        claim: ConnectorTargetSessionClaim,
        recovery_attempt_id: str,
        now: datetime,
    ) -> bool:
        async with self._lock:
            if self._claims.get(claim.verification_attempt_id) != claim or claim.expires_at > now:
                return False
            owner = self._recovery_owners.get(claim.verification_attempt_id)
            if owner is not None and owner[1] > now:
                return False
            self._recovery_owners[claim.verification_attempt_id] = (
                recovery_attempt_id,
                now + timedelta(minutes=5),
            )
            return True

    async def release_claim(
        self,
        claim: ConnectorTargetSessionClaim,
        *,
        now: datetime,
        recovery_attempt_id: str | None = None,
    ) -> bool:
        async with self._lock:
            owner = self._recovery_owners.get(claim.verification_attempt_id)
            if (owner[0] if owner is not None else None) != recovery_attempt_id or (
                owner is not None and owner[1] <= now
            ):
                return False
            return self._release_claim_unlocked(claim)

    async def publish(
        self,
        *,
        claim: ConnectorTargetSessionClaim,
        record: ConnectorTargetSessionVerificationRecord,
        now: datetime,
    ) -> bool:
        async with self._lock:
            if (
                self._claims.get(claim.verification_attempt_id) != claim
                or claim.verification_attempt_id in self._recovery_owners
                or claim.expires_at <= now
            ):
                return False
            if not self._add_unlocked(record, claim=claim):
                return False
            self._release_claim_unlocked(claim)
            return True

    def _add_unlocked(
        self,
        record: ConnectorTargetSessionVerificationRecord,
        *,
        claim: ConnectorTargetSessionClaim | None,
    ) -> bool:
        source_key = (
            record.organization_id,
            record.environment_id,
            record.source_runtime_activation_id,
        )
        create_key = (
            record.organization_id,
            record.environment_id,
            ConnectorTargetSessionService._identifier_digest(record.verified_by),
            record.idempotency_digest,
        )
        pending_source = self._claim_source_index.get(source_key)
        pending_create = self._claim_create_index.get(create_key)
        if (
            record.verification_id in self._records
            or source_key in self._source_index
            or create_key in self._create_index
            or (
                pending_source is not None
                and (claim is None or pending_source != claim.verification_attempt_id)
            )
            or (
                pending_create is not None
                and (claim is None or pending_create != claim.verification_attempt_id)
            )
        ):
            return False
        self._records[record.verification_id] = record
        self._source_index[source_key] = record.verification_id
        self._create_index[create_key] = record.verification_id
        return True

    def _release_claim_unlocked(self, claim: ConnectorTargetSessionClaim) -> bool:
        if self._claims.get(claim.verification_attempt_id) != claim:
            return False
        del self._claims[claim.verification_attempt_id]
        self._recovery_owners.pop(claim.verification_attempt_id, None)
        self._claim_source_index.pop(
            (claim.organization_id, claim.environment_id, claim.source_runtime_activation_id),
            None,
        )
        self._claim_create_index.pop(
            (
                claim.organization_id,
                claim.environment_id,
                claim.verified_by_digest,
                claim.idempotency_digest,
            ),
            None,
        )
        return True

    async def close(self) -> None:
        return None


class InMemoryConnectorTargetSessionProfileSource:
    def __init__(self, profiles: tuple[ConnectorTargetSessionProfileSnapshot, ...]) -> None:
        self._profiles = {item.profile_id: item for item in profiles}

    async def get_by_id(self, *, profile_id: str) -> ConnectorTargetSessionProfileSnapshot | None:
        return self._profiles.get(profile_id)

    async def get_by_id_in_scope(
        self,
        *,
        profile_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionProfileSnapshot | None:
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
    ) -> tuple[ConnectorTargetSessionProfileSnapshot, ...]:
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


class InMemoryConnectorTargetSessionPolicySource:
    def __init__(self, policies: tuple[ConnectorTargetSessionPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(self, *, policy_id: str) -> ConnectorTargetSessionPolicySnapshot | None:
        return self._policies.get(policy_id)

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionPolicySnapshot | None:
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
    ) -> tuple[ConnectorTargetSessionPolicySnapshot, ...]:
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
