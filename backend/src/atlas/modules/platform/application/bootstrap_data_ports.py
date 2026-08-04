from __future__ import annotations

from typing import Protocol

from atlas.modules.platform.domain.bootstrap_data_initialization import (
    BootstrapDataPlan,
    BootstrapMigrationSpec,
    DataInitializationReceipt,
    DataTargetState,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapDataCatalog(Protocol):
    def load(
        self, *, profile: DeploymentProfile, environment_id: str
    ) -> tuple[str, str, str, tuple[BootstrapMigrationSpec, ...]]: ...


class BootstrapDataTarget(Protocol):
    async def inspect(self, *, plan: BootstrapDataPlan) -> DataTargetState: ...

    async def initialize(
        self, *, execution_id: str, plan: BootstrapDataPlan, state_document: bytes
    ) -> DataInitializationReceipt: ...

    async def cleanup_attempt(self, execution_id: str) -> None: ...


class BootstrapDataError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
