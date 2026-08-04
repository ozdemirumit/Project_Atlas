from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.release_preflight import SHA256_PATTERN, DeploymentProfile


class TrustPlanState(StrEnum):
    PASSED = "passed"


class TrustAnchorPurpose(StrEnum):
    INTERNAL_SERVICE = "internal_service"


class TrustProvisioningState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TrustFileDisposition(StrEnum):
    PUBLISHED = "published"
    REUSED = "reused"


@dataclass(frozen=True, slots=True)
class TrustAnchorSpec:
    anchor_id: str
    source_id: str
    purpose: TrustAnchorPurpose
    subject_summary: str
    sha256: str
    not_before: datetime
    not_after: datetime
    non_production_only: bool
    certificate_pem: str = field(repr=False)

    def __post_init__(self) -> None:
        validate_stable_identifier(self.anchor_id, "trust anchor id")
        validate_stable_identifier(self.source_id, "trust source id")
        if not 1 <= len(self.subject_summary.strip()) <= 200:
            raise ValueError("trust anchor subject is outside platform bounds")
        if not SHA256_PATTERN.fullmatch(self.sha256):
            raise ValueError("trust anchor fingerprint is invalid")
        if self.not_before.tzinfo is None or self.not_after.tzinfo is None:
            raise ValueError("trust anchor validity must be timezone-aware")
        if self.not_after <= self.not_before:
            raise ValueError("trust anchor validity interval is invalid")
        if "PRIVATE KEY" in self.certificate_pem or not self.certificate_pem.endswith("\n"):
            raise ValueError("trust anchor contains unsafe material")


@dataclass(frozen=True, slots=True)
class BootstrapWorkloadIdentitySpec:
    identity_id: str
    service_id: str
    instance_id: str
    owner_subject_id: str
    purpose: str
    environment_id: str
    audiences: tuple[str, ...]
    secret_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for value, label in (
            (self.identity_id, "workload identity id"),
            (self.service_id, "workload service id"),
            (self.instance_id, "workload instance id"),
            (self.owner_subject_id, "workload owner subject id"),
            (self.environment_id, "workload environment id"),
        ):
            validate_stable_identifier(value, label)
        if not 1 <= len(self.purpose.strip()) <= 240:
            raise ValueError("workload identity purpose is outside platform bounds")
        if (
            not 1 <= len(self.audiences) <= 10
            or tuple(sorted(self.audiences)) != self.audiences
            or len(set(self.audiences)) != len(self.audiences)
        ):
            raise ValueError("workload identity audiences are invalid")
        if (
            not 1 <= len(self.secret_reference_ids) <= 20
            or tuple(sorted(self.secret_reference_ids)) != self.secret_reference_ids
            or len(set(self.secret_reference_ids)) != len(self.secret_reference_ids)
        ):
            raise ValueError("workload identity secret references are invalid")
        for audience in self.audiences:
            validate_stable_identifier(audience, "workload audience")
            if audience == "*" or audience.startswith("human."):
                raise ValueError("workload audience is unsafe")
        for reference in self.secret_reference_ids:
            validate_stable_identifier(reference, "workload secret reference")
            if not reference.startswith("secret."):
                raise ValueError("workload secrets require opaque references")


@dataclass(frozen=True, slots=True)
class BootstrapTrustPlan:
    schema_version: str
    release_id: str
    profile: DeploymentProfile
    organization_id: str
    environment_id: str
    site_id: str
    configuration_digest: str
    trust_plan_digest: str
    state: TrustPlanState
    result_code: str
    anchors: tuple[TrustAnchorSpec, ...]
    workload_identities: tuple[BootstrapWorkloadIdentitySpec, ...]
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.schema_version != "atlas.bootstrap-trust-plan.v1":
            raise ValueError("bootstrap trust plan schema is unsupported")
        for value, label in (
            (self.release_id, "release id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.site_id, "site id"),
            (self.result_code, "trust plan result code"),
        ):
            validate_stable_identifier(value, label)
        if not SHA256_PATTERN.fullmatch(self.configuration_digest) or not SHA256_PATTERN.fullmatch(
            self.trust_plan_digest
        ):
            raise ValueError("bootstrap trust plan digest is invalid")
        if self.generated_at.tzinfo is None:
            raise ValueError("bootstrap trust plan timestamp must be timezone-aware")
        if not 1 <= len(self.anchors) <= 16 or not 1 <= len(self.workload_identities) <= 32:
            raise ValueError("bootstrap trust plan inventory is outside platform bounds")
        anchor_ids = tuple(item.anchor_id for item in self.anchors)
        fingerprints = tuple(item.sha256 for item in self.anchors)
        identity_ids = tuple(item.identity_id for item in self.workload_identities)
        if (
            len(anchor_ids) != len(set(anchor_ids))
            or len(fingerprints) != len(set(fingerprints))
            or len(identity_ids) != len(set(identity_ids))
        ):
            raise ValueError("bootstrap trust plan inventory contains duplicates")


@dataclass(frozen=True, slots=True)
class TrustFileEvidence:
    file_id: str
    sha256: str
    size_bytes: int
    disposition: TrustFileDisposition

    def __post_init__(self) -> None:
        validate_stable_identifier(self.file_id, "trust file id")
        if not SHA256_PATTERN.fullmatch(self.sha256) or self.size_bytes < 1:
            raise ValueError("trust file evidence is invalid")


@dataclass(frozen=True, slots=True)
class TrustProvisioningExecution:
    execution_id: str
    phase_id: str
    release_id: str
    profile: DeploymentProfile
    configuration_digest: str
    trust_schema_version: str
    trust_plan_digest: str
    state: TrustProvisioningState
    result_code: str
    started_at: datetime
    completed_at: datetime | None
    anchor_count: int
    workload_identity_count: int
    evidence: tuple[TrustFileEvidence, ...]
    total_bytes: int

    def __post_init__(self) -> None:
        for value, label in (
            (self.execution_id, "execution id"),
            (self.phase_id, "phase id"),
            (self.release_id, "release id"),
            (self.trust_schema_version, "trust schema version"),
            (self.result_code, "result code"),
        ):
            validate_stable_identifier(value, label)
        if (
            self.phase_id != "phase.trust"
            or self.trust_schema_version != "atlas.bootstrap-trust-plan.v1"
        ):
            raise ValueError("trust provisioning phase identity is invalid")
        if not SHA256_PATTERN.fullmatch(self.configuration_digest) or not SHA256_PATTERN.fullmatch(
            self.trust_plan_digest
        ):
            raise ValueError("trust provisioning digest is invalid")
        if self.started_at.tzinfo is None or (
            self.completed_at is not None and self.completed_at.tzinfo is None
        ):
            raise ValueError("trust provisioning timestamps must be timezone-aware")
        if self.state is TrustProvisioningState.RUNNING:
            if (
                self.completed_at is not None
                or self.anchor_count != 0
                or self.workload_identity_count != 0
                or self.evidence
                or self.total_bytes != 0
            ):
                raise ValueError("running trust provisioning cannot contain final evidence")
        elif self.completed_at is None or self.completed_at < self.started_at:
            raise ValueError("finished trust provisioning requires a valid completion time")
        if self.state is TrustProvisioningState.COMPLETED:
            if (
                self.anchor_count < 1
                or self.workload_identity_count < 1
                or len(self.evidence) != 2
                or self.total_bytes != sum(item.size_bytes for item in self.evidence)
            ):
                raise ValueError("completed trust provisioning evidence is incomplete")
        elif (
            self.anchor_count != 0
            or self.workload_identity_count != 0
            or self.evidence
            or self.total_bytes != 0
        ):
            raise ValueError("failed trust provisioning cannot contain published evidence")


@dataclass(frozen=True, slots=True)
class TrustProvisioningReceipt:
    anchor_count: int
    workload_identity_count: int
    evidence: tuple[TrustFileEvidence, ...]

    def __post_init__(self) -> None:
        if self.anchor_count < 1 or self.workload_identity_count < 1 or len(self.evidence) != 2:
            raise ValueError("trust provisioning receipt is incomplete")
        file_ids = tuple(item.file_id for item in self.evidence)
        if len(file_ids) != len(set(file_ids)):
            raise ValueError("trust provisioning receipt contains duplicate files")

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.evidence)
