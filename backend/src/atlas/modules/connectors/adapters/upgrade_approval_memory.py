from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.upgrade_approval import (
    ConnectorUpgradeApprovalDecision,
    ConnectorUpgradeApprovalPolicySnapshot,
    ConnectorUpgradeApprovalRequest,
)


class InMemoryConnectorUpgradeApprovalRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorUpgradeApprovalRequest] = {}
        self._decisions: dict[str, ConnectorUpgradeApprovalDecision] = {}
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

    async def get_decision(self, *, request_id: str) -> ConnectorUpgradeApprovalDecision | None:
        return self._decisions.get(request_id)

    async def get_decision_by_key(
        self, *, decided_by: str, idempotency_key: str
    ) -> ConnectorUpgradeApprovalDecision | None:
        return next(
            (
                item
                for item in self._decisions.values()
                if item.decided_by == decided_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add_decision(self, decision: ConnectorUpgradeApprovalDecision) -> bool:
        async with self._lock:
            if decision.request_id in self._decisions or any(
                item.decided_by == decision.decided_by
                and item.idempotency_key == decision.idempotency_key
                for item in self._decisions.values()
            ):
                return False
            self._decisions[decision.request_id] = decision
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
