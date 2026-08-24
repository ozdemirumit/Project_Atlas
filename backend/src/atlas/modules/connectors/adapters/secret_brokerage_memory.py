from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
    ConnectorSecretBrokeragePolicySnapshot,
    ConnectorSecretBrokerageProfileSnapshot,
)


class InMemoryConnectorSecretBrokerageRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorSecretBrokerageAuthorizationRecord] = {}
        self._source_index: dict[tuple[str, str, str], str] = {}
        self._create_index: dict[tuple[str, str, str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, authorization_id: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        return self._records.get(authorization_id)

    async def get_in_scope(
        self,
        *,
        authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        record = self._records.get(authorization_id)
        if (
            record is None
            or record.organization_id != organization_id
            or record.environment_id != environment_id
        ):
            return None
        return record

    async def get_by_runtime_trust(
        self, *, source_runtime_trust_grant_id: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.source_runtime_trust_grant_id == source_runtime_trust_grant_id
            ),
            None,
        )

    async def get_by_runtime_trust_in_scope(
        self,
        *,
        source_runtime_trust_grant_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        authorization_id = self._source_index.get(
            (organization_id, environment_id, source_runtime_trust_grant_id)
        )
        return self._records.get(authorization_id) if authorization_id else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorSecretBrokerageAuthorizationRecord, ...]:
        return tuple(
            sorted(
                (
                    record
                    for record in self._records.values()
                    if record.organization_id == organization_id
                    and record.environment_id == environment_id
                ),
                key=lambda record: record.authorization_id,
            )
        )

    async def get_by_create_key(
        self, *, authorized_by: str, idempotency_key: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.authorized_by == authorized_by
                and record.idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_by_create_key_in_scope(
        self,
        *,
        authorized_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        authorization_id = self._create_index.get(
            (organization_id, environment_id, authorized_by, idempotency_key)
        )
        return self._records.get(authorization_id) if authorization_id else None

    async def add(self, record: ConnectorSecretBrokerageAuthorizationRecord) -> bool:
        async with self._lock:
            source_key = (
                record.organization_id,
                record.environment_id,
                record.source_runtime_trust_grant_id,
            )
            create_key = (
                record.organization_id,
                record.environment_id,
                record.authorized_by,
                record.idempotency_key,
            )
            if (
                record.authorization_id in self._records
                or source_key in self._source_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.authorization_id] = record
            self._source_index[source_key] = record.authorization_id
            self._create_index[create_key] = record.authorization_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorSecretBrokerageProfileSource:
    def __init__(self, profiles: tuple[ConnectorSecretBrokerageProfileSnapshot, ...]) -> None:
        self._profiles = profiles

    async def get_by_id(self, *, profile_id: str) -> ConnectorSecretBrokerageProfileSnapshot | None:
        return next((item for item in self._profiles if item.profile_id == profile_id), None)

    async def get_by_id_in_scope(
        self,
        *,
        profile_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorSecretBrokerageProfileSnapshot | None:
        return next(
            (
                profile
                for profile in self._profiles
                if profile.profile_id == profile_id
                and profile.organization_id == organization_id
                and profile.environment_id == environment_id
            ),
            None,
        )

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorSecretBrokerageProfileSnapshot, ...]:
        return tuple(
            sorted(
                (
                    profile
                    for profile in self._profiles
                    if profile.organization_id == organization_id
                    and profile.environment_id == environment_id
                ),
                key=lambda profile: profile.profile_id,
            )
        )


class InMemoryConnectorSecretBrokeragePolicySource:
    def __init__(self, policies: tuple[ConnectorSecretBrokeragePolicySnapshot, ...]) -> None:
        self._policies = policies

    async def get_by_id(self, *, policy_id: str) -> ConnectorSecretBrokeragePolicySnapshot | None:
        return next((item for item in self._policies if item.policy_id == policy_id), None)

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorSecretBrokeragePolicySnapshot | None:
        return next(
            (
                policy
                for policy in self._policies
                if policy.policy_id == policy_id
                and policy.organization_id == organization_id
                and policy.environment_id == environment_id
            ),
            None,
        )

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorSecretBrokeragePolicySnapshot, ...]:
        return tuple(
            sorted(
                (
                    policy
                    for policy in self._policies
                    if policy.organization_id == organization_id
                    and policy.environment_id == environment_id
                ),
                key=lambda policy: policy.policy_id,
            )
        )
