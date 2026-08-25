from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.credential_assignment import ConnectorCredentialProfileSnapshot
from atlas.modules.connectors.domain.runtime_activation import (
    ConnectorRuntimeActivationClaim,
    ConnectorRuntimeActivationInstruction,
    ConnectorRuntimeActivationPolicySnapshot,
    ConnectorRuntimeActivationProfileSnapshot,
    ConnectorRuntimeActivationReceipt,
    ConnectorRuntimeActivationRecord,
)
from atlas.modules.connectors.domain.runtime_deactivation import (
    ConnectorRuntimeDeactivationRecord,
)
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)


class ConnectorRuntimeActivationError(RuntimeError):
    pass


class ConnectorRuntimeActivationBrokerageRepository(Protocol):
    async def get_in_scope(
        self,
        *,
        authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None: ...


class ConnectorRuntimeActivationSource(Protocol):
    @property
    def repository(self) -> ConnectorRuntimeActivationBrokerageRepository: ...

    async def runtime_activation_source(
        self, *, authorization_id: str
    ) -> tuple[
        ConnectorSecretBrokerageAuthorizationRecord,
        ConnectorRuntimeTrustGrantRecord,
        ConnectorCredentialProfileSnapshot,
        frozenset[str],
    ]: ...

    async def capability_invocation_source(
        self, *, authorization_id: str
    ) -> tuple[
        ConnectorSecretBrokerageAuthorizationRecord,
        ConnectorRuntimeTrustGrantRecord,
        ConnectorCredentialProfileSnapshot,
        ConnectorCapabilityEnablementRecord,
        frozenset[str],
    ]: ...


class ConnectorRuntimeActivationProfileSource(Protocol):
    async def get_by_id(
        self, *, profile_id: str
    ) -> ConnectorRuntimeActivationProfileSnapshot | None: ...

    async def get_by_id_in_scope(
        self,
        *,
        profile_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationProfileSnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeActivationProfileSnapshot, ...]: ...


class ConnectorRuntimeActivationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorRuntimeActivationPolicySnapshot | None: ...

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationPolicySnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeActivationPolicySnapshot, ...]: ...


class ConnectorRuntimeActivator(Protocol):
    async def activate(
        self, instruction: ConnectorRuntimeActivationInstruction
    ) -> ConnectorRuntimeActivationReceipt: ...

    async def compensate(self, *, activation_attempt_id: str) -> None: ...


class ConnectorRuntimeActivationRepository(Protocol):
    async def get(self, *, activation_id: str) -> ConnectorRuntimeActivationRecord | None: ...

    async def get_in_scope(
        self,
        *,
        activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationRecord | None: ...

    async def get_by_brokerage_authorization(
        self, *, source_brokerage_authorization_id: str
    ) -> ConnectorRuntimeActivationRecord | None: ...

    async def get_by_brokerage_authorization_in_scope(
        self,
        *,
        source_brokerage_authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationRecord | None: ...

    async def get_by_create_key_in_scope(
        self,
        *,
        activated_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationRecord | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeActivationRecord, ...]: ...

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_brokerage_authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationClaim | None: ...

    async def claim(self, claim: ConnectorRuntimeActivationClaim) -> bool: ...

    async def fence_expired_claim(
        self,
        *,
        claim: ConnectorRuntimeActivationClaim,
        recovery_attempt_id: str,
        now: datetime,
    ) -> bool: ...

    async def release_claim(
        self,
        claim: ConnectorRuntimeActivationClaim,
        *,
        now: datetime,
        recovery_attempt_id: str | None = None,
    ) -> bool: ...

    async def publish(
        self,
        *,
        claim: ConnectorRuntimeActivationClaim,
        record: ConnectorRuntimeActivationRecord,
        now: datetime,
    ) -> bool: ...

    async def add(self, record: ConnectorRuntimeActivationRecord) -> bool: ...

    async def close(self) -> None: ...


class ConnectorRuntimeDeactivationStatusSource(Protocol):
    async def get_by_activation_in_scope(
        self,
        *,
        activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeDeactivationRecord | None: ...
