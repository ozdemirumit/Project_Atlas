from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementPolicySnapshot,
    ConnectorCapabilityEnablementRecord,
    ConnectorCapabilityProfileSnapshot,
)
from atlas.modules.connectors.domain.configuration_validation import (
    ConnectorConfigurationValidationRecord,
)
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
)


class ConnectorCapabilityEnablementError(RuntimeError):
    pass


class ConnectorCapabilityValidationSource(Protocol):
    async def capability_enablement_source(
        self, *, validation_id: str
    ) -> tuple[
        ConnectorConfigurationValidationRecord,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]: ...

    async def capability_enablement_source_in_scope(
        self,
        *,
        validation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[
        ConnectorConfigurationValidationRecord,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]: ...


class ConnectorCapabilityProfileSource(Protocol):
    async def get_by_id(self, *, profile_id: str) -> ConnectorCapabilityProfileSnapshot | None: ...

    async def get_by_id_in_scope(
        self,
        *,
        profile_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityProfileSnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorCapabilityProfileSnapshot, ...]: ...


class ConnectorCapabilityEnablementPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorCapabilityEnablementPolicySnapshot | None: ...

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementPolicySnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorCapabilityEnablementPolicySnapshot, ...]: ...


class ConnectorCapabilityEnablementRepository(Protocol):
    async def get(self, *, enablement_id: str) -> ConnectorCapabilityEnablementRecord | None: ...

    async def get_in_scope(
        self,
        *,
        enablement_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementRecord | None: ...

    async def get_by_validation(
        self, *, source_validation_id: str
    ) -> ConnectorCapabilityEnablementRecord | None: ...

    async def get_by_validation_in_scope(
        self,
        *,
        source_validation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementRecord | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorCapabilityEnablementRecord, ...]: ...

    async def get_by_create_key(
        self, *, enabled_by: str, idempotency_key: str
    ) -> ConnectorCapabilityEnablementRecord | None: ...

    async def get_by_create_key_in_scope(
        self,
        *,
        enabled_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementRecord | None: ...

    async def add(self, record: ConnectorCapabilityEnablementRecord) -> bool: ...

    async def close(self) -> None: ...
