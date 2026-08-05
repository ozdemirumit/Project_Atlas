from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class RunnerValidationOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class RunnerCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class RunnerCheckSeverity(StrEnum):
    INFORMATIONAL = "informational"
    ERROR = "error"


RUNNER_CHECK_CODES = (
    "runner.source.accepted",
    "runner.archive.integrity",
    "runner.process.isolation",
    "runner.environment.secret-free",
    "runner.authority.denied",
    "runner.package.import",
    "runner.quarantine.contract",
    "runner.capabilities.synthetic",
    "runner.output.bounded",
    "runner.workspace.cleaned",
)


@dataclass(frozen=True, slots=True)
class RunnerCheck:
    code: str
    state: RunnerCheckState
    severity: RunnerCheckSeverity
    summary: str
    remediation: str

    def __post_init__(self) -> None:
        if self.code not in RUNNER_CHECK_CODES:
            raise ValueError("Runner check code is invalid")
        if not self.summary.strip() or len(self.summary) > 500:
            raise ValueError("Runner check summary is invalid")
        if not self.remediation.strip() or len(self.remediation) > 500:
            raise ValueError("Runner check remediation is invalid")
        if self.state is RunnerCheckState.PASSED:
            if self.severity is not RunnerCheckSeverity.INFORMATIONAL:
                raise ValueError("Passed runner check severity is invalid")
        elif self.severity is not RunnerCheckSeverity.ERROR:
            raise ValueError("Failed runner check severity is invalid")


@dataclass(frozen=True, slots=True)
class RunnerExecutionResult:
    runtime_version: str
    adapter_contract: str
    harness_version: str
    checks: tuple[RunnerCheck, ...]
    capability_count: int
    invoked_capability_count: int
    fail_closed_count: int
    bounded_literal_count: int
    child_started: bool
    child_exit_code: int | None
    duration_ms: int
    output_digest: str
    output_size_bytes: int
    workspace_removed: bool

    def __post_init__(self) -> None:
        for value, name in (
            (self.runtime_version, "runner runtime version"),
            (self.adapter_contract, "runner adapter contract"),
            (self.harness_version, "runner harness version"),
        ):
            validate_stable_identifier(value, name)
        if tuple(item.code for item in self.checks) != RUNNER_CHECK_CODES[2:]:
            raise ValueError("Runner execution check set is invalid")
        if (
            min(
                self.capability_count,
                self.invoked_capability_count,
                self.fail_closed_count,
                self.bounded_literal_count,
                self.duration_ms,
                self.output_size_bytes,
            )
            < 0
        ):
            raise ValueError("Runner execution metrics are invalid")
        if self.invoked_capability_count > self.capability_count:
            raise ValueError("Runner invocation count is invalid")
        if self.fail_closed_count + self.bounded_literal_count != self.invoked_capability_count:
            raise ValueError("Runner behavior totals are invalid")
        if self.output_size_bytes > 65_536 or _DIGEST.fullmatch(self.output_digest) is None:
            raise ValueError("Runner output evidence is invalid")
        if not self.child_started and self.child_exit_code is not None:
            raise ValueError("Runner child status is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageRunnerValidation:
    validation_id: str
    schema_version: str
    version: int
    outcome: RunnerValidationOutcome
    source_contract_validation_id: str
    source_contract_validation_digest: str
    source_license_analysis_id: str
    source_license_analysis_digest: str
    source_inventory_id: str
    source_acquisition_id: str
    source_project_id: str
    source_contract_validated_by: str
    source_actor_set_digest: str
    organization_id: str
    environment_id: str
    validated_by: str
    validation_profile: str
    adapter_contract: str
    harness_version: str
    runtime_version: str
    package_digest: str
    package_size_bytes: int
    inventory_digest: str
    capability_count: int
    invoked_capability_count: int
    fail_closed_count: int
    bounded_literal_count: int
    checks: tuple[RunnerCheck, ...]
    child_started: bool
    child_exit_code: int | None
    duration_ms: int
    output_digest: str
    output_size_bytes: int
    workspace_removed: bool
    limitations: tuple[str, ...]
    promotion_blocked: bool
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    validated_at: datetime
    secret_content_scan_completed: bool = True
    prohibited_content_scan_completed: bool = True
    schema_semantic_validation_completed: bool = True
    permission_behavior_validation_completed: bool = True
    static_code_validation_completed: bool = True
    vulnerability_scan_completed: bool = True
    malware_scan_completed: bool = True
    license_scan_completed: bool = True
    contract_validation_completed: bool = True
    runner_validation_completed: bool = True
    lab_validation_completed: bool = False
    package_signed: bool = False
    publisher_attested: bool = False
    connector_rejected: bool = False
    connector_registered: bool = False
    connector_approved: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    target_configured: bool = False
    credentials_resolved: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.validation_id,
            self.schema_version,
            self.source_contract_validation_id,
            self.source_license_analysis_id,
            self.source_inventory_id,
            self.source_acquisition_id,
            self.source_project_id,
            self.source_contract_validated_by,
            self.organization_id,
            self.environment_id,
            self.validated_by,
            self.validation_profile,
            self.adapter_contract,
            self.harness_version,
            self.runtime_version,
        ):
            validate_stable_identifier(value, "runner validation identifier")
        for value in (
            self.source_contract_validation_digest,
            self.source_license_analysis_digest,
            self.source_actor_set_digest,
            self.package_digest,
            self.inventory_digest,
            self.output_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Runner validation digest is invalid")
        if self.version != 1 or tuple(item.code for item in self.checks) != RUNNER_CHECK_CODES:
            raise ValueError("Runner validation contract is invalid")
        passed = all(item.state is RunnerCheckState.PASSED for item in self.checks)
        if passed != (self.outcome is RunnerValidationOutcome.PASSED):
            raise ValueError("Runner validation outcome is inconsistent")
        if self.promotion_blocked != (self.outcome is RunnerValidationOutcome.FAILED):
            raise ValueError("Runner validation promotion state is inconsistent")
        if not self.workspace_removed:
            raise ValueError("Runner workspace cleanup is incomplete")
        if (
            min(
                self.package_size_bytes,
                self.capability_count,
                self.invoked_capability_count,
                self.fail_closed_count,
                self.bounded_literal_count,
                self.duration_ms,
                self.output_size_bytes,
            )
            < 0
            or self.package_size_bytes == 0
        ):
            raise ValueError("Runner validation metrics are invalid")
        if self.invoked_capability_count > self.capability_count:
            raise ValueError("Runner validation coverage is invalid")
        if self.fail_closed_count + self.bounded_literal_count != self.invoked_capability_count:
            raise ValueError("Runner validation behavior totals are invalid")
        if self.output_size_bytes > 65_536 or not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Runner validation request bounds are invalid")
        if self.validated_at.tzinfo is None or not self.limitations:
            raise ValueError("Runner validation evidence is incomplete")
        if len(self.limitations) != len(set(self.limitations)) or any(
            not item.strip() or len(item) > 500 for item in self.limitations
        ):
            raise ValueError("Runner validation limitations are invalid")
        if not all(
            (
                self.secret_content_scan_completed,
                self.prohibited_content_scan_completed,
                self.schema_semantic_validation_completed,
                self.permission_behavior_validation_completed,
                self.static_code_validation_completed,
                self.vulnerability_scan_completed,
                self.malware_scan_completed,
                self.license_scan_completed,
                self.contract_validation_completed,
                self.runner_validation_completed,
            )
        ):
            raise ValueError("Runner completion flags are invalid")
        if any(
            (
                self.lab_validation_completed,
                self.package_signed,
                self.publisher_attested,
                self.connector_rejected,
                self.connector_registered,
                self.connector_approved,
                self.connector_installed,
                self.connector_enabled,
                self.target_configured,
                self.credentials_resolved,
                self.runtime_trust_granted,
                self.execution_authorized,
                self.deployment_approved,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("Runner validation violates the no-authority boundary")
