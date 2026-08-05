from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.contract_validation import ConnectorPackageContractValidation
from atlas.modules.connectors.domain.runner_validation import (
    ConnectorPackageRunnerValidation,
    RunnerExecutionResult,
)


class PackageRunnerValidationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RunnerContractSource(Protocol):
    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageContractValidation | None: ...


class PackageRunnerValidationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageRunnerValidation | None: ...

    async def get_by_source_validation(
        self, *, source_contract_validation_id: str
    ) -> ConnectorPackageRunnerValidation | None: ...

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageRunnerValidation | None: ...

    async def add(self, validation: ConnectorPackageRunnerValidation) -> bool: ...

    async def close(self) -> None: ...


class PackageRunner(Protocol):
    async def run(
        self, *, files: dict[str, bytes], validation_profile: str
    ) -> RunnerExecutionResult: ...
