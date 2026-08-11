from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.upgrade_approval import (
    ConnectorUpgradeApprovalPolicySnapshot,
    ConnectorUpgradeApprovalRequest,
)


class InMemoryConnectorUpgradeApprovalRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorUpgradeApprovalRequest] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, request_id: str) -> ConnectorUpgradeApprovalRequest | None:
        return self._records.get(request_id)

    async def get_by_plan(self, *, plan_digest: str) -> ConnectorUpgradeApprovalRequest | None:
        return next(
            (item for item in self._records.values() if item.plan_digest == plan_digest), None
        )

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorUpgradeApprovalRequest | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.requested_by == requested_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, request: ConnectorUpgradeApprovalRequest) -> bool:
        async with self._lock:
            if request.request_id in self._records or any(
                item.plan_digest == request.plan_digest
                or (
                    item.requested_by == request.requested_by
                    and item.idempotency_key == request.idempotency_key
                )
                for item in self._records.values()
            ):
                return False
            self._records[request.request_id] = request
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorUpgradeApprovalPolicySource:
    def __init__(self, policies: tuple[ConnectorUpgradeApprovalPolicySnapshot, ...]) -> None:
        self._policies = policies

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorUpgradeApprovalPolicySnapshot, ...]:
        return tuple(
            item
            for item in self._policies
            if item.organization_id == organization_id and item.environment_id == environment_id
        )
