from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.target_configuration import (
    ConnectorTargetConfigurationBinding,
    ConnectorTargetConfigurationPolicySnapshot,
    ConnectorTargetProfileSnapshot,
)


class InMemoryConnectorTargetConfigurationRepository:
    def __init__(self) -> None:
        self._bindings: dict[str, ConnectorTargetConfigurationBinding] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, binding_id: str) -> ConnectorTargetConfigurationBinding | None:
        return self._bindings.get(binding_id)

    async def get_by_instance(
        self, *, source_instance_record_id: str
    ) -> ConnectorTargetConfigurationBinding | None:
        return next(
            (
                item
                for item in self._bindings.values()
                if item.source_instance_record_id == source_instance_record_id
            ),
            None,
        )

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorTargetConfigurationBinding, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._bindings.values()
                    if item.organization_id == organization_id
                    and item.environment_id == environment_id
                ),
                key=lambda item: item.binding_id,
            )
        )

    async def get_by_create_key(
        self, *, bound_by: str, idempotency_key: str
    ) -> ConnectorTargetConfigurationBinding | None:
        return next(
            (
                item
                for item in self._bindings.values()
                if item.bound_by == bound_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, binding: ConnectorTargetConfigurationBinding) -> bool:
        async with self._lock:
            if binding.binding_id in self._bindings:
                return False
            if any(
                item.source_instance_record_id == binding.source_instance_record_id
                or (
                    item.bound_by == binding.bound_by
                    and item.idempotency_key == binding.idempotency_key
                )
                for item in self._bindings.values()
            ):
                return False
            self._bindings[binding.binding_id] = binding
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorTargetProfileSource:
    def __init__(self, profiles: tuple[ConnectorTargetProfileSnapshot, ...]) -> None:
        self._profiles = {item.profile_id: item for item in profiles}

    async def get_by_id(self, *, profile_id: str) -> ConnectorTargetProfileSnapshot | None:
        return self._profiles.get(profile_id)

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorTargetProfileSnapshot, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._profiles.values()
                    if item.organization_id == organization_id
                    and item.environment_id == environment_id
                ),
                key=lambda item: item.profile_id,
            )
        )


class InMemoryConnectorTargetConfigurationPolicySource:
    def __init__(self, policies: tuple[ConnectorTargetConfigurationPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorTargetConfigurationPolicySnapshot | None:
        return self._policies.get(policy_id)

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorTargetConfigurationPolicySnapshot, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._policies.values()
                    if item.organization_id == organization_id
                    and item.environment_id == environment_id
                ),
                key=lambda item: item.policy_id,
            )
        )
