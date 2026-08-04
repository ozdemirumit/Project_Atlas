from __future__ import annotations

from typing import Protocol

from atlas.modules.platform.domain.bootstrap_service_deployment import (
    BootstrapServicePlan,
    BootstrapServiceSpec,
    ServiceDeploymentReceipt,
    ServiceTargetState,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BootstrapServiceCatalog(Protocol):
    def load(
        self, *, profile: DeploymentProfile, environment_id: str
    ) -> tuple[str, str, tuple[BootstrapServiceSpec, ...]]: ...


class BootstrapServiceTarget(Protocol):
    async def inspect(self, *, plan: BootstrapServicePlan) -> ServiceTargetState: ...

    async def deploy(
        self, *, execution_id: str, plan: BootstrapServicePlan, state_document: bytes
    ) -> ServiceDeploymentReceipt: ...

    async def cleanup_attempt(self, execution_id: str) -> None: ...
