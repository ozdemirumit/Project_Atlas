from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.upgrade_approval import (
    ConnectorUpgradeApprovalPolicySnapshot,
    ConnectorUpgradeApprovalRequest,
)


class ConnectorUpgradeApprovalError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ConnectorUpgradeApprovalPolicySource(Protocol):
    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorUpgradeApprovalPolicySnapshot, ...]: ...


class ConnectorUpgradeApprovalRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, request_id: str) -> ConnectorUpgradeApprovalRequest | None: ...

    async def get_by_plan(self, *, plan_digest: str) -> ConnectorUpgradeApprovalRequest | None: ...

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorUpgradeApprovalRequest | None: ...

    async def add(self, request: ConnectorUpgradeApprovalRequest) -> bool: ...

    async def close(self) -> None: ...
