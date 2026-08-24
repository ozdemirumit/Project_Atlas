from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementPolicySnapshot,
    ConnectorCapabilityEnablementRecord,
    ConnectorCapabilityProfileSnapshot,
)


class InMemoryConnectorCapabilityEnablementRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorCapabilityEnablementRecord] = {}
        self._validation_index: dict[tuple[str, str, str], str] = {}
        self._create_index: dict[tuple[str, str, str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, enablement_id: str) -> ConnectorCapabilityEnablementRecord | None:
        return self._records.get(enablement_id)

    async def get_in_scope(
        self,
        *,
        enablement_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementRecord | None:
        record = self._records.get(enablement_id)
        if (
            record is None
            or record.organization_id != organization_id
            or record.environment_id != environment_id
        ):
            return None
        return record

    async def get_by_validation(
        self, *, source_validation_id: str
    ) -> ConnectorCapabilityEnablementRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.source_validation_id == source_validation_id
            ),
            None,
        )

    async def get_by_validation_in_scope(
        self,
        *,
        source_validation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementRecord | None:
        enablement_id = self._validation_index.get(
            (organization_id, environment_id, source_validation_id)
        )
        return self._records.get(enablement_id) if enablement_id else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorCapabilityEnablementRecord, ...]:
        return tuple(
            sorted(
                (
                    record
                    for record in self._records.values()
                    if record.organization_id == organization_id
                    and record.environment_id == environment_id
                ),
                key=lambda record: record.enablement_id,
            )
        )

    async def get_by_create_key(
        self, *, enabled_by: str, idempotency_key: str
    ) -> ConnectorCapabilityEnablementRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.enabled_by == enabled_by and record.idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_by_create_key_in_scope(
        self,
        *,
        enabled_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementRecord | None:
        enablement_id = self._create_index.get(
            (organization_id, environment_id, enabled_by, idempotency_key)
        )
        return self._records.get(enablement_id) if enablement_id else None

    async def add(self, record: ConnectorCapabilityEnablementRecord) -> bool:
        async with self._lock:
            validation_key = (
                record.organization_id,
                record.environment_id,
                record.source_validation_id,
            )
            create_key = (
                record.organization_id,
                record.environment_id,
                record.enabled_by,
                record.idempotency_key,
            )
            if (
                record.enablement_id in self._records
                or validation_key in self._validation_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.enablement_id] = record
            self._validation_index[validation_key] = record.enablement_id
            self._create_index[create_key] = record.enablement_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorCapabilityProfileSource:
    def __init__(self, profiles: tuple[ConnectorCapabilityProfileSnapshot, ...]) -> None:
        self._profiles = profiles

    async def get_by_id(self, *, profile_id: str) -> ConnectorCapabilityProfileSnapshot | None:
        return next((item for item in self._profiles if item.profile_id == profile_id), None)

    async def get_by_id_in_scope(
        self,
        *,
        profile_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityProfileSnapshot | None:
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
    ) -> tuple[ConnectorCapabilityProfileSnapshot, ...]:
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


class InMemoryConnectorCapabilityEnablementPolicySource:
    def __init__(self, policies: tuple[ConnectorCapabilityEnablementPolicySnapshot, ...]) -> None:
        self._policies = policies

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorCapabilityEnablementPolicySnapshot | None:
        return next((item for item in self._policies if item.policy_id == policy_id), None)

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementPolicySnapshot | None:
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
    ) -> tuple[ConnectorCapabilityEnablementPolicySnapshot, ...]:
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
