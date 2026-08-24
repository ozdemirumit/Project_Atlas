from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.credential_assignment import ConnectorCredentialProfileSnapshot
from atlas.modules.connectors.domain.runtime_activation import ConnectorRuntimeActivationRecord
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionClaim,
    ConnectorTargetSessionInstruction,
    ConnectorTargetSessionPolicySnapshot,
    ConnectorTargetSessionProfileSnapshot,
    ConnectorTargetSessionReceipt,
    ConnectorTargetSessionVerificationRecord,
)


class ConnectorTargetSessionError(RuntimeError):
    pass


class ConnectorTargetSessionActivationRepository(Protocol):
    async def get_in_scope(
        self,
        *,
        activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationRecord | None: ...


class ConnectorTargetSessionSource(Protocol):
    @property
    def repository(self) -> ConnectorTargetSessionActivationRepository: ...

    async def target_session_source(
        self, *, activation_id: str
    ) -> tuple[
        ConnectorRuntimeActivationRecord,
        ConnectorSecretBrokerageAuthorizationRecord,
        ConnectorRuntimeTrustGrantRecord,
        ConnectorCredentialProfileSnapshot,
        frozenset[str],
    ]: ...

    async def capability_invocation_source(
        self, *, activation_id: str
    ) -> tuple[
        ConnectorRuntimeActivationRecord,
        ConnectorCapabilityEnablementRecord,
        frozenset[str],
    ]: ...


class ConnectorTargetSessionProfileSource(Protocol):
    async def get_by_id(
        self, *, profile_id: str
    ) -> ConnectorTargetSessionProfileSnapshot | None: ...

    async def get_by_id_in_scope(
        self,
        *,
        profile_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionProfileSnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorTargetSessionProfileSnapshot, ...]: ...


class ConnectorTargetSessionPolicySource(Protocol):
    async def get_by_id(self, *, policy_id: str) -> ConnectorTargetSessionPolicySnapshot | None: ...

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionPolicySnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorTargetSessionPolicySnapshot, ...]: ...


class ConnectorTargetSessionAdapter(Protocol):
    """Trusted adapter whose exact-attempt compensation must be bounded and idempotent."""

    async def verify(
        self, instruction: ConnectorTargetSessionInstruction
    ) -> ConnectorTargetSessionReceipt: ...

    async def compensate(self, *, verification_attempt_id: str) -> None:
        """Idempotently compensate only the exact verification attempt."""
        ...


class ConnectorTargetSessionRepository(Protocol):
    async def get(
        self, *, verification_id: str
    ) -> ConnectorTargetSessionVerificationRecord | None: ...

    async def get_in_scope(
        self,
        *,
        verification_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionVerificationRecord | None: ...

    async def get_by_runtime_activation(
        self, *, source_runtime_activation_id: str
    ) -> ConnectorTargetSessionVerificationRecord | None: ...

    async def get_by_runtime_activation_in_scope(
        self,
        *,
        source_runtime_activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionVerificationRecord | None: ...

    async def get_by_create_key(
        self, *, verified_by: str, idempotency_key: str
    ) -> ConnectorTargetSessionVerificationRecord | None: ...

    async def get_by_create_key_in_scope(
        self,
        *,
        verified_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionVerificationRecord | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorTargetSessionVerificationRecord, ...]: ...

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_runtime_activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionClaim | None: ...

    async def claim(self, claim: ConnectorTargetSessionClaim) -> bool: ...

    async def fence_expired_claim(
        self,
        *,
        claim: ConnectorTargetSessionClaim,
        recovery_attempt_id: str,
        now: datetime,
    ) -> bool: ...

    async def release_claim(
        self,
        claim: ConnectorTargetSessionClaim,
        *,
        now: datetime,
        recovery_attempt_id: str | None = None,
    ) -> bool: ...

    async def publish(
        self,
        *,
        claim: ConnectorTargetSessionClaim,
        record: ConnectorTargetSessionVerificationRecord,
        now: datetime,
    ) -> bool: ...

    async def add(self, record: ConnectorTargetSessionVerificationRecord) -> bool: ...

    async def close(self) -> None: ...
