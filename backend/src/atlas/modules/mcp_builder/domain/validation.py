from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.mcp_builder.domain.generation import validate_generated_path

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class BuilderValidationState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class BuilderValidationCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BuilderValidationSeverity(StrEnum):
    INFORMATIONAL = "informational"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class BuilderValidationCheck:
    code: str
    state: BuilderValidationCheckState
    severity: BuilderValidationSeverity
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.code, "validation check code")
        if not 1 <= len(self.summary) <= 300:
            raise ValueError("validation check summary is outside platform bounds")
        if not 0 <= len(self.evidence_paths) <= 20 or len(self.evidence_paths) != len(
            set(self.evidence_paths)
        ):
            raise ValueError("validation check evidence is outside platform bounds")
        for path in self.evidence_paths:
            validate_generated_path(path)
        if self.remediation is not None and not 1 <= len(self.remediation) <= 500:
            raise ValueError("validation check remediation is outside platform bounds")


@dataclass(frozen=True, slots=True)
class McpBuilderValidation:
    validation_id: str
    schema_version: str
    version: int
    state: BuilderValidationState
    project_id: str
    project_version: int
    project_digest: str
    source_digest: str
    checkpoint_id: str
    checkpoint_digest: str
    generation_id: str
    generation_digest: str
    artifact_digest: str
    organization_id: str
    environment_id: str
    validated_by: str
    language_profile: str
    template_version: str
    validation_profile: str
    validator_version: str
    checks: tuple[BuilderValidationCheck, ...]
    passed_count: int
    failed_count: int
    skipped_count: int
    limitations: tuple[str, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    completed_at: datetime
    validation_completed: bool = True
    static_validation_passed: bool = False
    runtime_self_test_performed: bool = False
    dependency_resolution_performed: bool = False
    domain_review_completed: bool = False
    security_review_completed: bool = False
    lab_validation_completed: bool = False
    candidate_package_created: bool = False
    connector_registered: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    network_request_performed: bool = False
    model_inference_performed: bool = False
    subprocess_invoked: bool = False
    dynamic_code_execution_performed: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.validation_id, "validation id"),
            (self.schema_version, "schema version"),
            (self.project_id, "project id"),
            (self.checkpoint_id, "checkpoint id"),
            (self.generation_id, "generation id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.validated_by, "validator subject id"),
            (self.language_profile, "language profile"),
            (self.template_version, "template version"),
            (self.validation_profile, "validation profile"),
            (self.validator_version, "validator version"),
        ):
            validate_stable_identifier(value, name)
        if self.version != 1 or self.project_version != 1:
            raise ValueError("Builder validation version is invalid")
        for value in (
            self.project_digest,
            self.source_digest,
            self.checkpoint_digest,
            self.generation_digest,
            self.artifact_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Builder validation digest is invalid")
        if not 1 <= len(self.checks) <= 64:
            raise ValueError("Builder validation check count is outside platform bounds")
        codes = [item.code for item in self.checks]
        if len(codes) != len(set(codes)):
            raise ValueError("Builder validation check codes must be unique")
        expected_passed = sum(
            item.state is BuilderValidationCheckState.PASSED for item in self.checks
        )
        expected_failed = sum(
            item.state is BuilderValidationCheckState.FAILED for item in self.checks
        )
        expected_skipped = sum(
            item.state is BuilderValidationCheckState.SKIPPED for item in self.checks
        )
        if (self.passed_count, self.failed_count, self.skipped_count) != (
            expected_passed,
            expected_failed,
            expected_skipped,
        ):
            raise ValueError("Builder validation totals are invalid")
        if self.state is BuilderValidationState.PASSED:
            if expected_failed or expected_skipped or not self.static_validation_passed:
                raise ValueError("Passing Builder validation contains incomplete checks")
        elif not expected_failed or self.static_validation_passed:
            raise ValueError("Failed Builder validation does not contain failed evidence")
        if (
            not 1 <= len(self.limitations) <= 20
            or len(self.limitations) != len(set(self.limitations))
            or any(not 1 <= len(item) <= 500 for item in self.limitations)
        ):
            raise ValueError("Builder validation limitations are invalid")
        if self.completed_at.tzinfo is None or not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Builder validation timestamp or idempotency key is invalid")
        if not self.validation_completed:
            raise ValueError("Builder validation must be complete")
        if any(
            (
                self.runtime_self_test_performed,
                self.dependency_resolution_performed,
                self.domain_review_completed,
                self.security_review_completed,
                self.lab_validation_completed,
                self.candidate_package_created,
                self.connector_registered,
                self.connector_installed,
                self.connector_enabled,
                self.network_request_performed,
                self.model_inference_performed,
                self.subprocess_invoked,
                self.dynamic_code_execution_performed,
                self.runtime_trust_granted,
                self.execution_authorized,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("Builder validation violates the static quarantine boundary")
