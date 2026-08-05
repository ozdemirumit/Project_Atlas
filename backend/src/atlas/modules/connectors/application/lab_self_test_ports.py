from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.lab_self_test import (
    ConnectorLabPlan,
    ConnectorPackageLabSelfTest,
    LabExecutionLease,
    LabExecutionResult,
)
from atlas.modules.connectors.domain.runner_validation import ConnectorPackageRunnerValidation


class PackageLabSelfTestError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class LabRunnerValidationSource(Protocol):
    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageRunnerValidation | None: ...


class ConnectorLabPlanSource(Protocol):
    async def get_by_id(self, *, plan_id: str) -> ConnectorLabPlan | None: ...


class LabAccessBroker(Protocol):
    async def issue(self, *, plan: ConnectorLabPlan) -> LabExecutionLease: ...

    async def release(self, *, lease: LabExecutionLease) -> bool: ...


class ConnectorLabRunner(Protocol):
    async def run(
        self,
        *,
        files: dict[str, bytes],
        plan: ConnectorLabPlan,
        lease: LabExecutionLease,
    ) -> LabExecutionResult: ...


class PackageLabSelfTestRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, self_test_id: str) -> ConnectorPackageLabSelfTest | None: ...

    async def get_by_source_validation(
        self, *, source_runner_validation_id: str
    ) -> ConnectorPackageLabSelfTest | None: ...

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageLabSelfTest | None: ...

    async def add(self, self_test: ConnectorPackageLabSelfTest) -> bool: ...

    async def close(self) -> None: ...
