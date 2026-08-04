from __future__ import annotations

from typing import Protocol

from atlas.modules.platform.domain.bootstrap_trust_provisioning import (
    BootstrapTrustPlan,
    BootstrapWorkloadIdentitySpec,
    TrustAnchorSpec,
    TrustProvisioningReceipt,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapTrustSource(Protocol):
    def load(
        self, *, profile: DeploymentProfile, environment_id: str
    ) -> tuple[tuple[TrustAnchorSpec, ...], tuple[BootstrapWorkloadIdentitySpec, ...]]: ...


class BootstrapTrustPublisher(Protocol):
    async def publish(
        self,
        *,
        execution_id: str,
        plan: BootstrapTrustPlan,
        trust_bundle: bytes,
        identity_catalog: bytes,
    ) -> TrustProvisioningReceipt: ...

    async def cleanup_attempt(self, execution_id: str) -> None: ...


class BootstrapTrustError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
