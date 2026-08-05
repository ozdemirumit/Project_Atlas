from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class BuilderLabValidationState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class BuilderLabCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BuilderLabCheckSeverity(StrEnum):
    INFO = "info"
    ERROR = "error"


class BuilderLabCheckCode(StrEnum):
    ARTIFACT_INTEGRITY = "lab.artifact_integrity"
    RUNNER_ISOLATION = "lab.runner_isolation"
    SECRET_FREE_ENVIRONMENT = "lab.secret_free_environment"
    NETWORK_DENIAL = "lab.network_denial"
    PACKAGE_IMPORT = "lab.package_import"
    QUARANTINE_CONTRACT = "lab.quarantine_contract"
    CAPABILITY_FAIL_CLOSED = "lab.capability_fail_closed"
    BOUNDED_OUTPUT = "lab.bounded_output"


@dataclass(frozen=True, slots=True)
class BuilderLabCheck:
    code: BuilderLabCheckCode
    state: BuilderLabCheckState
    severity: BuilderLabCheckSeverity
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str | None = None

    def __post_init__(self) -> None:
        if not self.summary.strip() or len(self.summary) > 800:
            raise ValueError("Builder lab check summary is outside platform bounds")
        if (
            len(self.evidence_paths) > 30
            or len(self.evidence_paths) != len(set(self.evidence_paths))
            or any(not value.strip() or len(value) > 500 for value in self.evidence_paths)
        ):
            raise ValueError("Builder lab check evidence paths are invalid")
        if self.state is BuilderLabCheckState.PASSED:
            if self.severity is not BuilderLabCheckSeverity.INFO or self.remediation is not None:
                raise ValueError("Passed builder lab check cannot retain remediation")
        elif (
            self.severity is not BuilderLabCheckSeverity.ERROR
            or self.remediation is None
            or not self.remediation.strip()
            or len(self.remediation) > 800
        ):
            raise ValueError("Non-passing builder lab check requires remediation")


@dataclass(frozen=True, slots=True)
class BuilderLabRunnerResult:
    checks: tuple[BuilderLabCheck, ...]
    runtime_version: str
    child_started: bool
    child_exit_code: int | None
    duration_ms: int
    output_digest: str
    output_size_bytes: int
    workspace_removed: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.runtime_version, "lab runtime version")
        if {item.code for item in self.checks} != set(BuilderLabCheckCode):
            raise ValueError("Builder lab runner checks are incomplete")
        if self.duration_ms < 0 or not 0 <= self.output_size_bytes <= 65_536:
            raise ValueError("Builder lab runner bounds are invalid")
        if _DIGEST.fullmatch(self.output_digest) is None:
            raise ValueError("Builder lab runner output digest is invalid")
        if not self.child_started and self.child_exit_code is not None:
            raise ValueError("Builder lab runner exit code is inconsistent")


@dataclass(frozen=True, slots=True)
class McpBuilderLabValidation:
    lab_validation_id: str
    schema_version: str
    version: int
    state: BuilderLabValidationState
    project_id: str
    project_version: int
    project_digest: str
    source_digest: str
    checkpoint_id: str
    checkpoint_digest: str
    generation_id: str
    generation_digest: str
    artifact_digest: str
    validation_id: str
    validation_digest: str
    domain_review_id: str
    domain_review_digest: str
    domain_reviewed_by: str
    security_review_id: str
    security_review_digest: str
    security_reviewed_by: str
    organization_id: str
    environment_id: str
    operated_by: str
    lab_profile: str
    runner_contract_version: str
    runtime_version: str
    checks: tuple[BuilderLabCheck, ...]
    passed_count: int
    failed_count: int
    skipped_count: int
    child_started: bool
    child_exit_code: int | None
    duration_ms: int
    output_digest: str
    output_size_bytes: int
    artifact_file_count: int
    artifact_size_bytes: int
    workspace_removed: bool
    limitations: tuple[str, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    completed_at: datetime
    lab_validation_completed: bool = True
    lab_validation_passed: bool = False
    synthetic_fixture_used: bool = True
    secret_values_present: bool = False
    target_connected: bool = False
    network_request_performed: bool = False
    runtime_self_test_performed: bool = False
    subprocess_invoked: bool = False
    dynamic_code_execution_performed: bool = False
    dependency_resolution_performed: bool = False
    malware_or_dynamic_scan_performed: bool = False
    candidate_package_created: bool = False
    connector_registered: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.lab_validation_id, "lab validation id"),
            (self.schema_version, "schema version"),
            (self.project_id, "project id"),
            (self.checkpoint_id, "checkpoint id"),
            (self.generation_id, "generation id"),
            (self.validation_id, "validation id"),
            (self.domain_review_id, "domain review id"),
            (self.domain_reviewed_by, "domain reviewer id"),
            (self.security_review_id, "security review id"),
            (self.security_reviewed_by, "security reviewer id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.operated_by, "lab operator id"),
            (self.lab_profile, "lab validation profile"),
            (self.runner_contract_version, "runner contract version"),
            (self.runtime_version, "runtime version"),
        ):
            validate_stable_identifier(value, name)
        if self.version != 1 or self.project_version != 1:
            raise ValueError("Builder lab validation version is invalid")
        for value in (
            self.project_digest,
            self.source_digest,
            self.checkpoint_digest,
            self.generation_digest,
            self.artifact_digest,
            self.validation_digest,
            self.domain_review_digest,
            self.security_review_digest,
            self.output_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Builder lab validation digest is invalid")
        if {item.code for item in self.checks} != set(BuilderLabCheckCode):
            raise ValueError("Builder lab validation checks are incomplete")
        expected_counts = (
            sum(item.state is BuilderLabCheckState.PASSED for item in self.checks),
            sum(item.state is BuilderLabCheckState.FAILED for item in self.checks),
            sum(item.state is BuilderLabCheckState.SKIPPED for item in self.checks),
        )
        if (self.passed_count, self.failed_count, self.skipped_count) != expected_counts:
            raise ValueError("Builder lab validation totals are invalid")
        passed = self.passed_count == len(BuilderLabCheckCode)
        if self.state is not (
            BuilderLabValidationState.PASSED if passed else BuilderLabValidationState.FAILED
        ):
            raise ValueError("Builder lab validation state is inconsistent")
        if self.lab_validation_passed != passed:
            raise ValueError("Builder lab validation pass flag is inconsistent")
        if self.operated_by in {self.domain_reviewed_by, self.security_reviewed_by}:
            raise ValueError("Builder lab validation violates separation of duties")
        if not self.lab_validation_completed or not self.workspace_removed:
            raise ValueError("Builder lab validation cleanup must complete")
        if self.duration_ms < 0 or self.artifact_file_count < 1 or self.artifact_size_bytes < 1:
            raise ValueError("Builder lab validation metrics are invalid")
        if not 0 <= self.output_size_bytes <= 65_536:
            raise ValueError("Builder lab validation output size is invalid")
        if not self.synthetic_fixture_used or self.secret_values_present or self.target_connected:
            raise ValueError("Builder lab validation violates the synthetic boundary")
        if not 1 <= len(self.limitations) <= 20 or len(self.limitations) != len(
            set(self.limitations)
        ):
            raise ValueError("Builder lab validation limitations are invalid")
        if any(not value.strip() or len(value) > 500 for value in self.limitations):
            raise ValueError("Builder lab validation limitations are invalid")
        if self.completed_at.tzinfo is None or not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Builder lab validation timestamp or idempotency key is invalid")
        if any(
            (
                self.network_request_performed,
                self.dependency_resolution_performed,
                self.malware_or_dynamic_scan_performed,
                self.candidate_package_created,
                self.connector_registered,
                self.connector_installed,
                self.connector_enabled,
                self.runtime_trust_granted,
                self.execution_authorized,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("Builder lab validation violates the no-authority boundary")
        if any(
            flag != self.child_started
            for flag in (
                self.runtime_self_test_performed,
                self.subprocess_invoked,
                self.dynamic_code_execution_performed,
            )
        ):
            raise ValueError("Builder lab validation execution flags are inconsistent")
        if not self.child_started and self.child_exit_code is not None:
            raise ValueError("Builder lab validation child state is inconsistent")
