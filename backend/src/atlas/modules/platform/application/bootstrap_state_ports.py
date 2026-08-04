from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

from atlas.modules.platform.domain.bootstrap_artifact_acquisition import (
    ArtifactAcquisitionExecution,
)
from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationRenderingExecution,
)
from atlas.modules.platform.domain.bootstrap_data_initialization import DataInitializationExecution
from atlas.modules.platform.domain.bootstrap_identity_handoff import IdentityHandoffExecution
from atlas.modules.platform.domain.bootstrap_integration_validation import (
    IntegrationValidationExecution,
)
from atlas.modules.platform.domain.bootstrap_service_deployment import ServiceDeploymentExecution
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapRunIdentity,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.bootstrap_trust_provisioning import TrustProvisioningExecution


class BootstrapStateRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def close(self) -> None: ...

    async def get_current(
        self, *, organization_id: str, environment_id: str, site_id: str
    ) -> BootstrapRunRecord | None: ...

    async def claim(
        self,
        *,
        identity: BootstrapRunIdentity,
        lease_holder_id: str,
        lease_duration: timedelta,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def checkpoint(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        phase_id: str,
        state: BootstrapCheckpointState,
        safe_output_references: tuple[str, ...],
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def begin_artifact_acquisition(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: ArtifactAcquisitionExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def finish_artifact_acquisition(
        self,
        *,
        run_id: str,
        execution: ArtifactAcquisitionExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def begin_configuration_rendering(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: ConfigurationRenderingExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def finish_configuration_rendering(
        self,
        *,
        run_id: str,
        execution: ConfigurationRenderingExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def begin_trust_provisioning(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: TrustProvisioningExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def finish_trust_provisioning(
        self,
        *,
        run_id: str,
        execution: TrustProvisioningExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def begin_data_initialization(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: DataInitializationExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def finish_data_initialization(
        self,
        *,
        run_id: str,
        execution: DataInitializationExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def begin_service_deployment(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: ServiceDeploymentExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def finish_service_deployment(
        self,
        *,
        run_id: str,
        execution: ServiceDeploymentExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def begin_identity_handoff(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: IdentityHandoffExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def finish_identity_handoff(
        self,
        *,
        run_id: str,
        execution: IdentityHandoffExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def begin_integration_validation(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: IntegrationValidationExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def finish_integration_validation(
        self,
        *,
        run_id: str,
        execution: IntegrationValidationExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def rebase(
        self,
        *,
        run_id: str,
        candidate: BootstrapRunIdentity,
        lease_holder_id: str,
        expected_version: int,
        preview_source_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...

    async def release(
        self,
        *,
        run_id: str,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult: ...


class BootstrapRepositoryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
