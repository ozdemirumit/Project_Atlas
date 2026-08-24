from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.invocation_authorization import (
    ConnectorInvocationAuthorizationPolicySnapshot,
    ConnectorInvocationAuthorizationRecord,
    ConnectorInvocationInputEnvelopeSnapshot,
    ConnectorInvocationProfileSnapshot,
)
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionVerificationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


class ConnectorInvocationAuthorizationError(RuntimeError):
    pass


class ConnectorInvocationAuthorizationTargetSessionRepository(Protocol):
    async def get_in_scope(
        self,
        *,
        verification_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionVerificationRecord | None: ...


class ConnectorInvocationAuthorizationSource(Protocol):
    @property
    def repository(self) -> ConnectorInvocationAuthorizationTargetSessionRepository: ...

    async def capability_invocation_authorization_source(
        self,
        *,
        verification_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[
        ConnectorTargetSessionVerificationRecord,
        ConnectorCapabilityEnablementRecord,
        frozenset[str],
    ]: ...


class ConnectorInvocationProfileSource(Protocol):
    async def get_by_id_in_scope(
        self, *, profile_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationProfileSnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationProfileSnapshot, ...]: ...


class ConnectorInvocationInputEnvelopeSource(Protocol):
    async def get_by_id_in_scope(
        self, *, envelope_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationInputEnvelopeSnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationInputEnvelopeSnapshot, ...]: ...


class ConnectorInvocationAuthorizationPolicySource(Protocol):
    async def get_by_id_in_scope(
        self, *, policy_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationAuthorizationPolicySnapshot | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationAuthorizationPolicySnapshot, ...]: ...


class ConnectorInvocationEvidencePreparer(Protocol):
    async def prepare(
        self,
        *,
        source: ConnectorTargetSessionVerificationRecord,
        enablement: ConnectorCapabilityEnablementRecord,
        issued_at: datetime,
    ) -> None: ...


class ConnectorCapabilityPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        permission_id: str,
        capability_id: str,
        capability_class: str,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class ConnectorInvocationAuthorizationRepository(Protocol):
    async def get_in_scope(
        self,
        *,
        authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationAuthorizationRecord | None: ...

    async def get_by_target_session_in_scope(
        self,
        *,
        source_target_session_verification_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationAuthorizationRecord | None: ...

    async def get_by_create_key_in_scope(
        self,
        *,
        authorized_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationAuthorizationRecord | None: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationAuthorizationRecord, ...]: ...

    async def add(self, record: ConnectorInvocationAuthorizationRecord) -> bool: ...

    async def close(self) -> None: ...
