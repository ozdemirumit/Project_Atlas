from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import (
    ArtifactAcquisitionExecution,
)
from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationRenderingExecution,
)
from atlas.modules.platform.domain.bootstrap_data_initialization import DataInitializationExecution
from atlas.modules.platform.domain.bootstrap_plan import DIGEST_PATTERN
from atlas.modules.platform.domain.bootstrap_service_deployment import ServiceDeploymentExecution
from atlas.modules.platform.domain.bootstrap_trust_provisioning import TrustProvisioningExecution
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapCheckpointState(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class BootstrapRunState(StrEnum):
    ACTIVE = "active"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class BootstrapRunIdentity:
    release_id: str
    profile: DeploymentProfile
    organization_id: str
    environment_id: str
    site_id: str
    plan_digest: str
    resume_key: str
    configuration_digest: str
    phase_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for value, label in (
            (self.release_id, "release_id"),
            (self.organization_id, "organization_id"),
            (self.environment_id, "environment_id"),
            (self.site_id, "site_id"),
            (self.resume_key, "resume_key"),
        ):
            validate_stable_identifier(value, label)
        if not DIGEST_PATTERN.fullmatch(self.plan_digest) or not DIGEST_PATTERN.fullmatch(
            self.configuration_digest
        ):
            raise ValueError("bootstrap state digest is invalid")
        if (
            not self.phase_ids
            or len(self.phase_ids) > 32
            or len(set(self.phase_ids)) != len(self.phase_ids)
        ):
            raise ValueError("bootstrap phase order is invalid")
        for phase_id in self.phase_ids:
            validate_stable_identifier(phase_id, "phase_id")


@dataclass(frozen=True, slots=True)
class BootstrapPhaseCheckpoint:
    phase_id: str
    state: BootstrapCheckpointState
    safe_output_references: tuple[str, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.phase_id, "phase_id")
        if self.recorded_at.tzinfo is None:
            raise ValueError("checkpoint timestamp must be timezone-aware")
        if len(self.safe_output_references) > 20 or len(set(self.safe_output_references)) != len(
            self.safe_output_references
        ):
            raise ValueError("checkpoint output references are invalid")
        for reference in self.safe_output_references:
            validate_stable_identifier(reference, "safe_output_reference")
            if not reference.startswith(("evidence.", "result.", "artifact.")):
                raise ValueError("checkpoint output must be an opaque safe reference")


@dataclass(frozen=True, slots=True)
class BootstrapRunRecord:
    run_id: str
    version: int
    identity: BootstrapRunIdentity
    state: BootstrapRunState
    checkpoints: tuple[BootstrapPhaseCheckpoint, ...]
    lease_holder_id: str | None
    lease_acquired_at: datetime | None
    lease_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    artifact_acquisition: ArtifactAcquisitionExecution | None = None
    configuration_rendering: ConfigurationRenderingExecution | None = None
    trust_provisioning: TrustProvisioningExecution | None = None
    data_initialization: DataInitializationExecution | None = None
    service_deployment: ServiceDeploymentExecution | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.run_id, "run_id")
        if self.version < 1:
            raise ValueError("bootstrap run version must be positive")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("bootstrap run timestamps must be timezone-aware")
        lease_values = (
            self.lease_holder_id,
            self.lease_acquired_at,
            self.lease_expires_at,
        )
        if any(value is None for value in lease_values) != all(
            value is None for value in lease_values
        ):
            raise ValueError("bootstrap lease fields must be set together")
        if self.lease_holder_id is not None:
            validate_stable_identifier(self.lease_holder_id, "lease_holder_id")
            assert self.lease_acquired_at is not None and self.lease_expires_at is not None
            if self.lease_acquired_at.tzinfo is None or self.lease_expires_at.tzinfo is None:
                raise ValueError("bootstrap lease timestamps must be timezone-aware")
            if self.lease_expires_at <= self.lease_acquired_at:
                raise ValueError("bootstrap lease expiry must follow acquisition")
        checkpoint_ids = tuple(item.phase_id for item in self.checkpoints)
        if len(checkpoint_ids) != len(set(checkpoint_ids)) or any(
            item not in self.identity.phase_ids for item in checkpoint_ids
        ):
            raise ValueError("bootstrap checkpoints do not match the plan")
        if self.artifact_acquisition is not None:
            artifact_execution = self.artifact_acquisition
            if (
                artifact_execution.release_id != self.identity.release_id
                or artifact_execution.phase_id not in self.identity.phase_ids
            ):
                raise ValueError("artifact acquisition does not match the bootstrap run")
        if self.configuration_rendering is not None:
            configuration_execution = self.configuration_rendering
            if (
                configuration_execution.release_id != self.identity.release_id
                or configuration_execution.profile is not self.identity.profile
                or configuration_execution.configuration_digest
                != self.identity.configuration_digest
                or configuration_execution.phase_id not in self.identity.phase_ids
            ):
                raise ValueError("configuration rendering does not match the bootstrap run")
        if self.trust_provisioning is not None:
            trust_execution = self.trust_provisioning
            if (
                trust_execution.release_id != self.identity.release_id
                or trust_execution.profile is not self.identity.profile
                or trust_execution.configuration_digest != self.identity.configuration_digest
                or trust_execution.phase_id not in self.identity.phase_ids
            ):
                raise ValueError("trust provisioning does not match the bootstrap run")
        if self.data_initialization is not None:
            data_execution = self.data_initialization
            if (
                data_execution.release_id != self.identity.release_id
                or data_execution.profile is not self.identity.profile
                or data_execution.configuration_digest != self.identity.configuration_digest
                or data_execution.phase_id not in self.identity.phase_ids
            ):
                raise ValueError("data initialization does not match the bootstrap run")
        if self.service_deployment is not None:
            service_execution = self.service_deployment
            if (
                service_execution.release_id != self.identity.release_id
                or service_execution.profile is not self.identity.profile
                or service_execution.configuration_digest != self.identity.configuration_digest
                or service_execution.phase_id not in self.identity.phase_ids
            ):
                raise ValueError("service deployment does not match the bootstrap run")

    def lease_is_active(self, at: datetime) -> bool:
        return self.lease_expires_at is not None and at < self.lease_expires_at

    @property
    def completed_phase_ids(self) -> tuple[str, ...]:
        return tuple(
            item.phase_id
            for item in self.checkpoints
            if item.state is BootstrapCheckpointState.COMPLETED
        )

    @property
    def failed_phase_id(self) -> str | None:
        return next(
            (
                item.phase_id
                for item in self.checkpoints
                if item.state is BootstrapCheckpointState.FAILED
            ),
            None,
        )

    @property
    def current_phase_id(self) -> str | None:
        completed = set(self.completed_phase_ids)
        return next((item for item in self.identity.phase_ids if item not in completed), None)


@dataclass(frozen=True, slots=True)
class BootstrapStateView:
    record: BootstrapRunRecord | None
    durable: bool
    lease_available: bool
    lease_held_by_current_actor: bool
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False


@dataclass(frozen=True, slots=True)
class BootstrapMutationResult:
    record: BootstrapRunRecord
    replayed: bool
    reclaimed_expired_lease: bool = False
    preserved_checkpoint_phase_ids: tuple[str, ...] = ()
    invalidated_checkpoint_phase_ids: tuple[str, ...] = ()
    invalidation_reason_codes: tuple[str, ...] = ()
    earliest_affected_phase_id: str | None = None
    artifact_acquisition: ArtifactAcquisitionExecution | None = None
    configuration_rendering: ConfigurationRenderingExecution | None = None
    trust_provisioning: TrustProvisioningExecution | None = None
    data_initialization: DataInitializationExecution | None = None
    service_deployment: ServiceDeploymentExecution | None = None
