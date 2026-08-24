from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.runtime_trust import (
    ConnectorRuntimeTrustGrantRecord,
    ConnectorRuntimeTrustPolicySnapshot,
    ConnectorRuntimeTrustProfileSnapshot,
)


class InMemoryConnectorRuntimeTrustRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorRuntimeTrustGrantRecord] = {}
        self._enablement_index: dict[tuple[str, str, str], str] = {}
        self._create_index: dict[tuple[str, str, str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, grant_id: str) -> ConnectorRuntimeTrustGrantRecord | None:
        return self._records.get(grant_id)

    async def get_in_scope(
        self,
        *,
        grant_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeTrustGrantRecord | None:
        record = self._records.get(grant_id)
        if (
            record is None
            or record.organization_id != organization_id
            or record.environment_id != environment_id
        ):
            return None
        return record

    async def get_by_enablement(
        self, *, source_enablement_id: str
    ) -> ConnectorRuntimeTrustGrantRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.source_enablement_id == source_enablement_id
            ),
            None,
        )

    async def get_by_enablement_in_scope(
        self,
        *,
        source_enablement_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeTrustGrantRecord | None:
        grant_id = self._enablement_index.get(
            (organization_id, environment_id, source_enablement_id)
        )
        return self._records.get(grant_id) if grant_id else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeTrustGrantRecord, ...]:
        return tuple(
            sorted(
                (
                    record
                    for record in self._records.values()
                    if record.organization_id == organization_id
                    and record.environment_id == environment_id
                ),
                key=lambda record: record.grant_id,
            )
        )

    async def get_by_create_key(
        self, *, granted_by: str, idempotency_key: str
    ) -> ConnectorRuntimeTrustGrantRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.granted_by == granted_by and record.idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_by_create_key_in_scope(
        self,
        *,
        granted_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeTrustGrantRecord | None:
        grant_id = self._create_index.get(
            (organization_id, environment_id, granted_by, idempotency_key)
        )
        return self._records.get(grant_id) if grant_id else None

    async def add(self, record: ConnectorRuntimeTrustGrantRecord) -> bool:
        async with self._lock:
            enablement_key = (
                record.organization_id,
                record.environment_id,
                record.source_enablement_id,
            )
            create_key = (
                record.organization_id,
                record.environment_id,
                record.granted_by,
                record.idempotency_key,
            )
            if (
                record.grant_id in self._records
                or enablement_key in self._enablement_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.grant_id] = record
            self._enablement_index[enablement_key] = record.grant_id
            self._create_index[create_key] = record.grant_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorRuntimeTrustProfileSource:
    def __init__(self, profiles: tuple[ConnectorRuntimeTrustProfileSnapshot, ...]) -> None:
        self._profiles = profiles

    async def get_by_id(self, *, profile_id: str) -> ConnectorRuntimeTrustProfileSnapshot | None:
        return next((item for item in self._profiles if item.profile_id == profile_id), None)

    async def get_by_id_in_scope(
        self,
        *,
        profile_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeTrustProfileSnapshot | None:
        return next(
            (
                item
                for item in self._profiles
                if item.profile_id == profile_id
                and item.organization_id == organization_id
                and item.environment_id == environment_id
            ),
            None,
        )

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeTrustProfileSnapshot, ...]:
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


class InMemoryConnectorRuntimeTrustPolicySource:
    def __init__(self, policies: tuple[ConnectorRuntimeTrustPolicySnapshot, ...]) -> None:
        self._policies = policies

    async def get_by_id(self, *, policy_id: str) -> ConnectorRuntimeTrustPolicySnapshot | None:
        return next((item for item in self._policies if item.policy_id == policy_id), None)

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeTrustPolicySnapshot | None:
        return next(
            (
                item
                for item in self._policies
                if item.policy_id == policy_id
                and item.organization_id == organization_id
                and item.environment_id == environment_id
            ),
            None,
        )

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeTrustPolicySnapshot, ...]:
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
