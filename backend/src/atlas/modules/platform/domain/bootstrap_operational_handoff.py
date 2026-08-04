from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.release_preflight import SHA256_PATTERN, DeploymentProfile


class HandoffPlanState(StrEnum):
    PASSED = "passed"


class HandoffTargetState(StrEnum):
    EMPTY = "empty"
    REUSABLE = "reusable"


class HandoffExecutionState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class HandoffCheckState(StrEnum):
    PASSED = "passed"
    NOT_APPLICABLE = "not_applicable"


class HandoffReportDisposition(StrEnum):
    PUBLISHED = "published"
    REUSED = "reused"


class HandoffReadinessClass(StrEnum):
    DEVELOPER_LINUX_LAB_BOOTSTRAP_COMPLETE = "developer_linux_lab_bootstrap_complete"


@dataclass(frozen=True, slots=True)
class HandoffReadinessClaims:
    production_ready: bool = False
    customer_integrations_validated: bool = False
    support_accepted: bool = False
    ha_certified: bool = False
    dr_certified: bool = False
    backup_restore_validated: bool = False
    release_approved: bool = False

    def __post_init__(self) -> None:
        if any(
            (
                self.production_ready,
                self.customer_integrations_validated,
                self.support_accepted,
                self.ha_certified,
                self.dr_certified,
                self.backup_restore_validated,
                self.release_approved,
            )
        ):
            raise ValueError("bootstrap handoff cannot assert production readiness")


@dataclass(frozen=True, slots=True)
class OperationalHandoffCheck:
    check_id: str
    category_id: str
    subject_id: str
    state: HandoffCheckState
    result_code: str
    mandatory: bool

    def __post_init__(self) -> None:
        for value, label in (
            (self.check_id, "handoff check id"),
            (self.category_id, "handoff category id"),
            (self.subject_id, "handoff subject id"),
            (self.result_code, "handoff result code"),
        ):
            validate_stable_identifier(value, label)
        if self.mandatory != (self.state is HandoffCheckState.PASSED):
            raise ValueError("handoff check applicability is invalid")


@dataclass(frozen=True, slots=True)
class BootstrapHandoffPlan:
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
    verification_report_digest: str
    source_evidence_digest: str
    handoff_plan_digest: str
    ingress_contract_id: str
    target_id: str
    target_kind: str
    target_state: HandoffTargetState
    readiness_class: HandoffReadinessClass
    readiness_claims: HandoffReadinessClaims
    known_limitation_ids: tuple[str, ...]
    pending_action_ids: tuple[str, ...]
    owner_role_ids: tuple[str, ...]
    missing_production_evidence_ids: tuple[str, ...]
    checks: tuple[OperationalHandoffCheck, ...]
    state: HandoffPlanState
    result_code: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if (
            self.schema_version != "atlas.bootstrap-handoff-plan.v1"
            or self.suite_version != "atlas.bootstrap-handoff-suite.v1"
        ):
            raise ValueError("bootstrap handoff plan schema is unsupported")
        for value, label in (
            (self.release_id, "release id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.site_id, "site id"),
            (self.source_run_id, "source run id"),
            (self.ingress_contract_id, "ingress contract id"),
            (self.target_id, "handoff target id"),
            (self.target_kind, "handoff target kind"),
            (self.result_code, "handoff result code"),
        ):
            validate_stable_identifier(value, label)
        if self.source_run_version < 1 or self.generated_at.tzinfo is None:
            raise ValueError("bootstrap handoff source metadata is invalid")
        digests = (
            self.configuration_digest,
            self.trust_plan_digest,
            self.data_plan_digest,
            self.service_plan_digest,
            self.identity_plan_digest,
            self.integration_plan_digest,
            self.verification_plan_digest,
            self.verification_report_digest,
            self.source_evidence_digest,
            self.handoff_plan_digest,
        )
        if any(not SHA256_PATTERN.fullmatch(value) for value in digests):
            raise ValueError("bootstrap handoff plan digest is invalid")
        self._validate_catalogs()

    def _validate_catalogs(self) -> None:
        if len(self.checks) != 15 or len({item.check_id for item in self.checks}) != 15:
            raise ValueError("bootstrap handoff catalog is incomplete")
        expected_lengths = (
            (self.known_limitation_ids, 7),
            (self.pending_action_ids, 7),
            (self.owner_role_ids, 5),
            (self.missing_production_evidence_ids, 7),
        )
        for values, expected in expected_lengths:
            if len(values) != expected or len(set(values)) != len(values):
                raise ValueError("bootstrap handoff catalog is incomplete")
            for value in values:
                validate_stable_identifier(value, "handoff catalog id")
        if (
            sum(item.state is HandoffCheckState.PASSED for item in self.checks) != 12
            or sum(item.state is HandoffCheckState.NOT_APPLICABLE for item in self.checks) != 3
        ):
            raise ValueError("bootstrap handoff verdict is incomplete")


@dataclass(frozen=True, slots=True)
class HandoffReportEvidence:
    evidence_id: str
    sha256: str
    size_bytes: int
    disposition: HandoffReportDisposition

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_id, "handoff report evidence id")
        if not SHA256_PATTERN.fullmatch(self.sha256) or self.size_bytes < 1:
            raise ValueError("handoff report evidence is invalid")


@dataclass(frozen=True, slots=True)
class OperationalHandoffExecution:
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
    verification_plan_digest: str
    verification_report_digest: str
    source_evidence_digest: str
    handoff_schema_version: str
    suite_version: str
    handoff_plan_digest: str
    target_id: str
    readiness_class: HandoffReadinessClass
    readiness_claims: HandoffReadinessClaims
    state: HandoffExecutionState
    result_code: str
    started_at: datetime
    completed_at: datetime | None
    passed_count: int
    not_applicable_count: int
    mandatory_pass_count: int
    known_limitation_count: int
    pending_action_count: int
    owner_role_count: int
    missing_production_evidence_count: int
    external_operation_count: int
    checks: tuple[OperationalHandoffCheck, ...]
    evidence: tuple[HandoffReportEvidence, ...]

    def __post_init__(self) -> None:
        for value, label in (
            (self.execution_id, "execution id"),
            (self.phase_id, "phase id"),
            (self.release_id, "release id"),
            (self.handoff_schema_version, "handoff schema version"),
            (self.suite_version, "handoff suite version"),
            (self.target_id, "handoff target id"),
            (self.result_code, "handoff result code"),
        ):
            validate_stable_identifier(value, label)
        if (
            self.phase_id != "phase.handoff"
            or self.handoff_schema_version != "atlas.bootstrap-handoff-plan.v1"
            or self.suite_version != "atlas.bootstrap-handoff-suite.v1"
        ):
            raise ValueError("handoff execution identity is invalid")
        digests = (
            self.configuration_digest,
            self.trust_plan_digest,
            self.data_plan_digest,
            self.service_plan_digest,
            self.identity_plan_digest,
            self.integration_plan_digest,
            self.verification_plan_digest,
            self.verification_report_digest,
            self.source_evidence_digest,
            self.handoff_plan_digest,
        )
        if any(not SHA256_PATTERN.fullmatch(value) for value in digests):
            raise ValueError("handoff execution digest is invalid")
        if self.started_at.tzinfo is None or (
            self.completed_at is not None and self.completed_at.tzinfo is None
        ):
            raise ValueError("handoff timestamps must be timezone-aware")
        final_values = (
            self.passed_count,
            self.not_applicable_count,
            self.mandatory_pass_count,
            self.known_limitation_count,
            self.pending_action_count,
            self.owner_role_count,
            self.missing_production_evidence_count,
            bool(self.checks),
            bool(self.evidence),
        )
        if self.external_operation_count:
            raise ValueError("handoff performed a forbidden external operation")
        if self.state is HandoffExecutionState.RUNNING:
            if self.completed_at is not None or any(final_values):
                raise ValueError("running handoff cannot contain final evidence")
        elif self.completed_at is None or self.completed_at < self.started_at:
            raise ValueError("finished handoff requires a completion time")
        if self.state is HandoffExecutionState.COMPLETED:
            if final_values != (12, 3, 12, 7, 7, 5, 7, True, True):
                raise ValueError("completed handoff evidence is incomplete")
            if len(self.checks) != 15 or len(self.evidence) != 1:
                raise ValueError("completed handoff evidence is incomplete")
        elif any(final_values):
            raise ValueError("failed handoff cannot contain successful evidence")


@dataclass(frozen=True, slots=True)
class OperationalHandoffReceipt:
    checks: tuple[OperationalHandoffCheck, ...]
    evidence: tuple[HandoffReportEvidence, ...]

    def __post_init__(self) -> None:
        if (
            len(self.checks) != 15
            or sum(item.state is HandoffCheckState.PASSED for item in self.checks) != 12
            or sum(item.state is HandoffCheckState.NOT_APPLICABLE for item in self.checks) != 3
            or len(self.evidence) != 1
        ):
            raise ValueError("operational handoff receipt is incomplete")
