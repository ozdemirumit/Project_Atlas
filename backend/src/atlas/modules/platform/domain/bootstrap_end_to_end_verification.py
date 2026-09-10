from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.release_preflight import SHA256_PATTERN, DeploymentProfile


class VerificationPlanState(StrEnum):
    PASSED = "passed"


class VerificationTargetState(StrEnum):
    EMPTY = "empty"
    REUSABLE = "reusable"


class VerificationExecutionState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class VerificationCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"


class VerificationReportDisposition(StrEnum):
    PUBLISHED = "published"
    REUSED = "reused"


@dataclass(frozen=True, slots=True)
class EndToEndVerificationCheck:
    check_id: str
    category_id: str
    subject_id: str
    state: VerificationCheckState
    result_code: str
    mandatory: bool

    def __post_init__(self) -> None:
        for value, label in (
            (self.check_id, "verification check id"),
            (self.category_id, "verification category id"),
            (self.subject_id, "verification subject id"),
            (self.result_code, "verification result code"),
        ):
            validate_stable_identifier(value, label)


@dataclass(frozen=True, slots=True)
class BootstrapVerificationPlan:
    schema_version: str
    suite_version: str
    release_id: str
    profile: DeploymentProfile
    organization_id: str
    environment_id: str
    site_id: str
    source_run_id: str
    source_run_version: int
    configuration_digest: str
    trust_plan_digest: str
    data_plan_digest: str
    service_plan_digest: str
    identity_plan_digest: str
    integration_plan_digest: str
    verification_plan_digest: str
    ingress_contract_id: str
    target_id: str
    target_kind: str
    target_state: VerificationTargetState
    checks: tuple[EndToEndVerificationCheck, ...]
    state: VerificationPlanState
    result_code: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if (
            self.schema_version != "atlas.bootstrap-verification-plan.v1"
            or self.suite_version != "atlas.bootstrap-verification-suite.v1"
        ):
            raise ValueError("bootstrap verification plan schema is unsupported")
        for value, label in (
            (self.release_id, "release id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.site_id, "site id"),
            (self.source_run_id, "source run id"),
            (self.ingress_contract_id, "ingress contract id"),
            (self.target_id, "verification target id"),
            (self.target_kind, "verification target kind"),
            (self.result_code, "verification result code"),
        ):
            validate_stable_identifier(value, label)
        if self.source_run_version < 1 or self.generated_at.tzinfo is None:
            raise ValueError("bootstrap verification source metadata is invalid")
        if any(
            not SHA256_PATTERN.fullmatch(value)
            for value in (
                self.configuration_digest,
                self.trust_plan_digest,
                self.data_plan_digest,
                self.service_plan_digest,
                self.identity_plan_digest,
                self.integration_plan_digest,
                self.verification_plan_digest,
            )
        ):
            raise ValueError("bootstrap verification plan digest is invalid")
        if len(self.checks) != 15:
            raise ValueError("bootstrap verification catalog is incomplete")
        check_ids = tuple(item.check_id for item in self.checks)
        if len(set(check_ids)) != len(check_ids):
            raise ValueError("bootstrap verification catalog contains duplicate checks")
        mandatory_count = sum(item.mandatory for item in self.checks)
        optional_count = len(self.checks) - mandatory_count
        if mandatory_count != 12 or optional_count != 3:
            raise ValueError("bootstrap verification catalog composition is invalid")


@dataclass(frozen=True, slots=True)
class VerificationReportEvidence:
    evidence_id: str
    sha256: str
    size_bytes: int
    disposition: VerificationReportDisposition

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_id, "verification report evidence id")
        if not SHA256_PATTERN.fullmatch(self.sha256) or self.size_bytes < 1:
            raise ValueError("verification report evidence is invalid")


@dataclass(frozen=True, slots=True)
class EndToEndVerificationExecution:
    execution_id: str
    phase_id: str
    release_id: str
    profile: DeploymentProfile
    configuration_digest: str
    trust_plan_digest: str
    data_plan_digest: str
    service_plan_digest: str
    identity_plan_digest: str
    integration_plan_digest: str
    verification_schema_version: str
    suite_version: str
    verification_plan_digest: str
    target_id: str
    state: VerificationExecutionState
    result_code: str
    started_at: datetime
    completed_at: datetime | None
    passed_count: int
    failed_count: int
    skipped_count: int
    not_applicable_count: int
    mandatory_pass_count: int
    unresolved_mandatory_count: int
    external_operation_count: int
    checks: tuple[EndToEndVerificationCheck, ...]
    evidence: tuple[VerificationReportEvidence, ...]

    def __post_init__(self) -> None:
        for value, label in (
            (self.execution_id, "execution id"),
            (self.phase_id, "phase id"),
            (self.release_id, "release id"),
            (self.verification_schema_version, "verification schema version"),
            (self.suite_version, "verification suite version"),
            (self.target_id, "verification target id"),
            (self.result_code, "verification result code"),
        ):
            validate_stable_identifier(value, label)
        if (
            self.phase_id != "phase.verify"
            or self.verification_schema_version != "atlas.bootstrap-verification-plan.v1"
            or self.suite_version != "atlas.bootstrap-verification-suite.v1"
        ):
            raise ValueError("verification execution identity is invalid")
        if any(
            not SHA256_PATTERN.fullmatch(value)
            for value in (
                self.configuration_digest,
                self.trust_plan_digest,
                self.data_plan_digest,
                self.service_plan_digest,
                self.identity_plan_digest,
                self.integration_plan_digest,
                self.verification_plan_digest,
            )
        ):
            raise ValueError("verification execution digest is invalid")
        if self.started_at.tzinfo is None or (
            self.completed_at is not None and self.completed_at.tzinfo is None
        ):
            raise ValueError("verification timestamps must be timezone-aware")
        if self.external_operation_count:
            raise ValueError("verification performed a forbidden external operation")
        empty_evidence = (
            self.passed_count == 0
            and self.failed_count == 0
            and self.skipped_count == 0
            and self.not_applicable_count == 0
            and self.mandatory_pass_count == 0
            and self.unresolved_mandatory_count == 0
            and not self.checks
            and not self.evidence
        )
        if self.state is VerificationExecutionState.RUNNING:
            if self.completed_at is not None or not empty_evidence:
                raise ValueError("running verification cannot contain final evidence")
            return
        if self.completed_at is None or self.completed_at < self.started_at:
            raise ValueError("finished verification requires a completion time")
        if self.state is VerificationExecutionState.FAILED and empty_evidence:
            # The execution was abandoned (e.g. a reclaimed lease) before any
            # check was ever evaluated. That is a legitimate empty failure,
            # distinct from a failure that ran checks but hid the results.
            return
        passed = sum(item.state is VerificationCheckState.PASSED for item in self.checks)
        failed = sum(item.state is VerificationCheckState.FAILED for item in self.checks)
        skipped = sum(item.state is VerificationCheckState.SKIPPED for item in self.checks)
        not_applicable = sum(
            item.state is VerificationCheckState.NOT_APPLICABLE for item in self.checks
        )
        mandatory_pass = sum(
            item.mandatory and item.state is VerificationCheckState.PASSED for item in self.checks
        )
        unresolved_mandatory = sum(
            item.mandatory
            and item.state in (VerificationCheckState.FAILED, VerificationCheckState.SKIPPED)
            for item in self.checks
        )
        if (
            len(self.checks) != 15
            or self.passed_count != passed
            or self.failed_count != failed
            or self.skipped_count != skipped
            or self.not_applicable_count != not_applicable
            or self.mandatory_pass_count != mandatory_pass
            or self.unresolved_mandatory_count != unresolved_mandatory
        ):
            raise ValueError("verification counts are inconsistent with recorded checks")
        if self.state is VerificationExecutionState.COMPLETED:
            if unresolved_mandatory != 0 or len(self.evidence) != 1:
                raise ValueError("completed verification cannot have unresolved mandatory checks")
        elif unresolved_mandatory == 0 and failed == 0:
            raise ValueError(
                "failed verification must show a real failed or unresolved mandatory check"
            )


@dataclass(frozen=True, slots=True)
class EndToEndVerificationReceipt:
    checks: tuple[EndToEndVerificationCheck, ...]
    evidence: tuple[VerificationReportEvidence, ...]

    def __post_init__(self) -> None:
        if len(self.checks) != 15 or len(self.evidence) != 1:
            raise ValueError("end-to-end verification receipt is incomplete")
        unresolved_mandatory = sum(
            item.mandatory
            and item.state in (VerificationCheckState.FAILED, VerificationCheckState.SKIPPED)
            for item in self.checks
        )
        if unresolved_mandatory:
            raise ValueError(
                "end-to-end verification receipt cannot publish unresolved mandatory checks"
            )
