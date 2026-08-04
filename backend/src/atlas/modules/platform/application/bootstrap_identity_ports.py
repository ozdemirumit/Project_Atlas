from __future__ import annotations

from typing import Protocol

from atlas.modules.platform.domain.bootstrap_identity_handoff import (
    BootstrapIdentityGroupMapping,
    BootstrapIdentityPlan,
    IdentityHandoffReceipt,
    IdentityTargetState,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapIdentityError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BootstrapIdentityCatalog(Protocol):
    def load(
        self, *, profile: DeploymentProfile, environment_id: str
    ) -> tuple[str, str, str, str, str, str, str, tuple[BootstrapIdentityGroupMapping, ...]]: ...


class BootstrapIdentityTarget(Protocol):
    async def inspect(self, *, plan: BootstrapIdentityPlan) -> IdentityTargetState: ...

    async def publish(
        self, *, execution_id: str, plan: BootstrapIdentityPlan, state_document: bytes
    ) -> IdentityHandoffReceipt: ...

    async def cleanup_attempt(self, execution_id: str) -> None: ...
