from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.package_approval import (
    ConnectorPackageApprovalDecision,
    ConnectorPackageApprovalPolicySnapshot,
    ConnectorPackageApprovalRequest,
)


class InMemoryPackageApprovalRepository:
    def __init__(self) -> None:
        self._requests: dict[str, ConnectorPackageApprovalRequest] = {}
        self._source_index: dict[str, str] = {}
        self._request_create_index: dict[tuple[str, str], str] = {}
        self._decisions: dict[str, ConnectorPackageApprovalDecision] = {}
        self._decision_create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_request(self, *, request_id: str) -> ConnectorPackageApprovalRequest | None:
        return self._requests.get(request_id)

    async def get_request_by_source(
        self, *, source_final_validation_id: str
    ) -> ConnectorPackageApprovalRequest | None:
        request_id = self._source_index.get(source_final_validation_id)
        return self._requests.get(request_id) if request_id else None

    async def get_request_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorPackageApprovalRequest | None:
        request_id = self._request_create_index.get((requested_by, idempotency_key))
        return self._requests.get(request_id) if request_id else None

    async def add_request(self, request: ConnectorPackageApprovalRequest) -> bool:
        async with self._lock:
            create_key = (request.requested_by, request.idempotency_key)
            if (
                request.request_id in self._requests
                or request.source_final_validation_id in self._source_index
                or create_key in self._request_create_index
            ):
                return False
            self._requests[request.request_id] = request
            self._source_index[request.source_final_validation_id] = request.request_id
            self._request_create_index[create_key] = request.request_id
            return True

    async def get_decision(self, *, request_id: str) -> ConnectorPackageApprovalDecision | None:
        return self._decisions.get(request_id)

    async def get_decision_by_create_key(
        self, *, decided_by: str, idempotency_key: str
    ) -> ConnectorPackageApprovalDecision | None:
        request_id = self._decision_create_index.get((decided_by, idempotency_key))
        return self._decisions.get(request_id) if request_id else None

    async def add_decision(self, decision: ConnectorPackageApprovalDecision) -> bool:
        async with self._lock:
            create_key = (decision.decided_by, decision.idempotency_key)
            if decision.request_id in self._decisions or create_key in self._decision_create_index:
                return False
            self._decisions[decision.request_id] = decision
            self._decision_create_index[create_key] = decision.request_id
            return True

    async def close(self) -> None:
        return None


class InMemoryPackageApprovalPolicySource:
    def __init__(self, policies: tuple[ConnectorPackageApprovalPolicySnapshot, ...] = ()) -> None:
        self._records = {item.policy_id: item for item in policies}

    async def get_by_id(self, *, policy_id: str) -> ConnectorPackageApprovalPolicySnapshot | None:
        return self._records.get(policy_id)

    async def add(self, policy: ConnectorPackageApprovalPolicySnapshot) -> bool:
        if policy.policy_id in self._records:
            return False
        self._records[policy.policy_id] = policy
        return True
