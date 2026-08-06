from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.credential_assignment import (
    ConnectorCredentialAssignmentPolicySnapshot,
    ConnectorCredentialAssignmentRecord,
    ConnectorCredentialProfileSnapshot,
)
from atlas.modules.connectors.domain.target_configuration import ConnectorTargetConfigurationBinding


class ConnectorCredentialAssignmentError(RuntimeError):
    pass


class ConnectorCredentialTargetSource(Protocol):
    async def credential_assignment_source(
        self, *, binding_id: str
    ) -> tuple[ConnectorTargetConfigurationBinding, frozenset[str]]: ...


class ConnectorCredentialProfileSource(Protocol):
    async def get_by_id(self, *, profile_id: str) -> ConnectorCredentialProfileSnapshot | None: ...


class ConnectorCredentialAssignmentPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorCredentialAssignmentPolicySnapshot | None: ...


class ConnectorCredentialAssignmentRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, assignment_id: str) -> ConnectorCredentialAssignmentRecord | None: ...

    async def get_by_target_binding(
        self, *, source_target_binding_id: str
    ) -> ConnectorCredentialAssignmentRecord | None: ...

    async def get_by_create_key(
        self, *, assigned_by: str, idempotency_key: str
    ) -> ConnectorCredentialAssignmentRecord | None: ...

    async def add(self, record: ConnectorCredentialAssignmentRecord) -> bool: ...

    async def close(self) -> None: ...
