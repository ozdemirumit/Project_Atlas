from __future__ import annotations

from typing import Protocol

from atlas.modules.platform.domain.bootstrap_integration_validation import (
    BootstrapIntegrationPlan,
    CoreIntegrationRegistration,
    IntegrationTargetState,
    IntegrationValidationCheck,
    IntegrationValidationReceipt,
    ModelEndpointRegistration,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapIntegrationError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class BootstrapIntegrationCatalog(Protocol):
    def load(
        self, *, profile: DeploymentProfile, environment_id: str
    ) -> tuple[
        str,
        str,
        ModelEndpointRegistration,
        tuple[CoreIntegrationRegistration, ...],
        tuple[IntegrationValidationCheck, ...],
    ]: ...


class BootstrapIntegrationTarget(Protocol):
    async def inspect(self, *, plan: BootstrapIntegrationPlan) -> IntegrationTargetState: ...

    async def publish(
        self, *, execution_id: str, plan: BootstrapIntegrationPlan, state_document: bytes
    ) -> IntegrationValidationReceipt: ...

    async def cleanup_attempt(self, execution_id: str) -> None: ...
