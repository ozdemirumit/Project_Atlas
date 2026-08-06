from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.final_validation import ConnectorPackageFinalValidation
from atlas.modules.connectors.domain.package_approval import (
    ConnectorPackageApprovalDecision,
    ConnectorPackageApprovalPolicySnapshot,
    ConnectorPackageApprovalRequest,
)


class PackageApprovalError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PackageApprovalPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorPackageApprovalPolicySnapshot | None: ...


class PackageApprovalFinalValidationSource(Protocol):
    async def approval_source(
        self, *, validation_id: str
    ) -> tuple[ConnectorPackageFinalValidation, frozenset[str]]: ...


class PackageApprovalRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_request(self, *, request_id: str) -> ConnectorPackageApprovalRequest | None: ...

    async def get_request_by_source(
        self, *, source_final_validation_id: str
    ) -> ConnectorPackageApprovalRequest | None: ...

    async def get_request_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorPackageApprovalRequest | None: ...

    async def add_request(self, request: ConnectorPackageApprovalRequest) -> bool: ...

    async def get_decision(self, *, request_id: str) -> ConnectorPackageApprovalDecision | None: ...

    async def get_decision_by_create_key(
        self, *, decided_by: str, idempotency_key: str
    ) -> ConnectorPackageApprovalDecision | None: ...

    async def add_decision(self, decision: ConnectorPackageApprovalDecision) -> bool: ...

    async def close(self) -> None: ...
