from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.release_preflight import SHA256_PATTERN, DeploymentProfile


class ServicePlanState(StrEnum):
    PASSED = "passed"


class ServiceTargetState(StrEnum):
    EMPTY = "empty"
    REUSABLE = "reusable"


class ServiceEndpointClass(StrEnum):
    PRIVATE = "private"


class ServiceRuntimeState(StrEnum):
    READY = "ready"


class ServiceDeploymentState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ServiceStateDisposition(StrEnum):
    PUBLISHED = "published"
    REUSED = "reused"


@dataclass(frozen=True, slots=True)
class BootstrapServiceSpec:
    service_id: str
    sequence: int
    artifact_id: str
    artifact_sha256: str
    dependencies: tuple[str, ...]
    workload_identity_id: str | None
    endpoint_class: ServiceEndpointClass
    cpu_limit_millicores: int
    memory_limit_mb: int
    startup_probe_id: str
    readiness_probe_id: str
    liveness_probe_id: str
    run_as_root: bool = False
    privileged: bool = False
    arbitrary_public_egress: bool = False

    def __post_init__(self) -> None:
        for value, label in (
            (self.service_id, "service id"),
            (self.artifact_id, "service artifact id"),
            (self.startup_probe_id, "startup probe id"),
            (self.readiness_probe_id, "readiness probe id"),
            (self.liveness_probe_id, "liveness probe id"),
        ):
            validate_stable_identifier(value, label)
        if self.workload_identity_id is not None:
            validate_stable_identifier(self.workload_identity_id, "workload identity id")
        if self.sequence < 1 or not SHA256_PATTERN.fullmatch(self.artifact_sha256):
            raise ValueError("service sequence or artifact checksum is invalid")
        if any(item == self.service_id for item in self.dependencies):
            raise ValueError("service cannot depend on itself")
        for dependency in self.dependencies:
            validate_stable_identifier(dependency, "service dependency")
        if len(self.dependencies) != len(set(self.dependencies)):
            raise ValueError("service dependencies contain duplicates")
        if not 50 <= self.cpu_limit_millicores <= 4000:
            raise ValueError("service CPU limit is outside platform bounds")
        if not 64 <= self.memory_limit_mb <= 8192:
            raise ValueError("service memory limit is outside platform bounds")
        if self.run_as_root or self.privileged or self.arbitrary_public_egress:
            raise ValueError("service runtime policy is unsafe")


@dataclass(frozen=True, slots=True)
class BootstrapServicePlan:
    schema_version: str
    release_id: str
    profile: DeploymentProfile
    organization_id: str
    environment_id: str
    site_id: str
    configuration_digest: str
    trust_plan_digest: str
    data_plan_digest: str
    migration_artifact_digest: str
    service_plan_digest: str
    target_id: str
    target_kind: str
    target_state: ServiceTargetState
    state: ServicePlanState
    result_code: str
    services: tuple[BootstrapServiceSpec, ...]
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.schema_version != "atlas.bootstrap-service-plan.v1":
            raise ValueError("bootstrap service plan schema is unsupported")
        for value, label in (
            (self.release_id, "release id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.site_id, "site id"),
            (self.target_id, "service target id"),
            (self.target_kind, "service target kind"),
            (self.result_code, "service plan result code"),
        ):
            validate_stable_identifier(value, label)
        digests = (
            self.configuration_digest,
            self.trust_plan_digest,
            self.data_plan_digest,
            self.migration_artifact_digest,
            self.service_plan_digest,
        )
        if any(not SHA256_PATTERN.fullmatch(value) for value in digests):
            raise ValueError("bootstrap service plan digest is invalid")
        if self.generated_at.tzinfo is None or not 1 <= len(self.services) <= 32:
            raise ValueError("bootstrap service plan metadata is invalid")
        ids = tuple(item.service_id for item in self.services)
        sequences = tuple(item.sequence for item in self.services)
        if len(ids) != len(set(ids)) or sequences != tuple(range(1, len(ids) + 1)):
            raise ValueError("service catalog identity or order is invalid")
        seen: set[str] = set()
        for service in self.services:
            if any(dependency not in seen for dependency in service.dependencies):
                raise ValueError("service dependency order is invalid")
            seen.add(service.service_id)


@dataclass(frozen=True, slots=True)
class ServiceStatusEvidence:
    service_id: str
    state: ServiceRuntimeState
    startup_passed: bool
    readiness_passed: bool
    liveness_passed: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.service_id, "service status id")
        if not (self.startup_passed and self.readiness_passed and self.liveness_passed):
            raise ValueError("ready service requires passing probe evidence")


@dataclass(frozen=True, slots=True)
class ServiceStateEvidence:
    evidence_id: str
    sha256: str
    size_bytes: int
    disposition: ServiceStateDisposition

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_id, "service evidence id")
        if not SHA256_PATTERN.fullmatch(self.sha256) or self.size_bytes < 1:
            raise ValueError("service state evidence is invalid")


@dataclass(frozen=True, slots=True)
class ServiceDeploymentExecution:
    execution_id: str
    phase_id: str
    release_id: str
    profile: DeploymentProfile
    configuration_digest: str
    trust_plan_digest: str
    data_plan_digest: str
    migration_artifact_digest: str
    service_schema_version: str
    service_plan_digest: str
    target_id: str
    state: ServiceDeploymentState
    result_code: str
    started_at: datetime
    completed_at: datetime | None
    deployed_service_count: int
    ready_service_count: int
    passed_probe_count: int
    service_statuses: tuple[ServiceStatusEvidence, ...]
    evidence: tuple[ServiceStateEvidence, ...]

    def __post_init__(self) -> None:
        for value, label in (
            (self.execution_id, "execution id"),
            (self.phase_id, "phase id"),
            (self.release_id, "release id"),
            (self.service_schema_version, "service schema version"),
            (self.target_id, "service target id"),
            (self.result_code, "service result code"),
        ):
            validate_stable_identifier(value, label)
        if (
            self.phase_id != "phase.services"
            or self.service_schema_version != "atlas.bootstrap-service-plan.v1"
        ):
            raise ValueError("service deployment phase identity is invalid")
        digests = (
            self.configuration_digest,
            self.trust_plan_digest,
            self.data_plan_digest,
            self.migration_artifact_digest,
            self.service_plan_digest,
        )
        if any(not SHA256_PATTERN.fullmatch(value) for value in digests):
            raise ValueError("service deployment digest is invalid")
        if self.started_at.tzinfo is None or (
            self.completed_at is not None and self.completed_at.tzinfo is None
        ):
            raise ValueError("service deployment timestamps must be timezone-aware")
        if self.state is ServiceDeploymentState.RUNNING:
            if (
                self.completed_at
                or self.deployed_service_count
                or self.ready_service_count
                or self.passed_probe_count
                or self.service_statuses
                or self.evidence
            ):
                raise ValueError("running service deployment cannot contain final evidence")
        elif self.completed_at is None or self.completed_at < self.started_at:
            raise ValueError("finished service deployment requires a valid completion time")
        if self.state is ServiceDeploymentState.COMPLETED:
            expected = len(self.service_statuses)
            if (
                expected < 1
                or self.deployed_service_count != expected
                or self.ready_service_count != expected
                or self.passed_probe_count != expected * 3
                or len(self.evidence) != 1
            ):
                raise ValueError("completed service deployment evidence is incomplete")
        elif (
            self.deployed_service_count
            or self.ready_service_count
            or self.passed_probe_count
            or self.service_statuses
            or self.evidence
        ):
            raise ValueError("failed service deployment cannot contain verified evidence")


@dataclass(frozen=True, slots=True)
class ServiceDeploymentReceipt:
    service_statuses: tuple[ServiceStatusEvidence, ...]
    evidence: tuple[ServiceStateEvidence, ...]

    def __post_init__(self) -> None:
        if not self.service_statuses or len(self.evidence) != 1:
            raise ValueError("service deployment receipt is incomplete")
