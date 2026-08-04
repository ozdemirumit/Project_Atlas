from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.release_preflight import SHA256_PATTERN, DeploymentProfile


class IntegrationPlanState(StrEnum):
    PASSED = "passed"


class IntegrationTargetState(StrEnum):
    EMPTY = "empty"
    REUSABLE = "reusable"


class IntegrationValidationState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IntegrationCheckState(StrEnum):
    PASSED = "passed"
    NOT_APPLICABLE = "not_applicable"


class IntegrationActivationState(StrEnum):
    INACTIVE = "inactive"


class IntegrationStateDisposition(StrEnum):
    PUBLISHED = "published"
    REUSED = "reused"


@dataclass(frozen=True, slots=True)
class ModelEndpointRegistration:
    endpoint_id: str
    owner_id: str
    provider_type: str
    service_reference_id: str
    credential_reference_id: str
    model_id: str
    context_limit: int
    output_limit: int
    data_classification_ceiling: str
    residency_boundary_id: str
    timeout_seconds: int
    max_retries: int
    rate_limit_per_minute: int
    concurrency_limit: int
    telemetry_classification: str
    approved_task_class_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for value, label in (
            (self.endpoint_id, "model endpoint id"),
            (self.owner_id, "model endpoint owner"),
            (self.provider_type, "model provider type"),
            (self.service_reference_id, "model service reference"),
            (self.credential_reference_id, "model credential reference"),
            (self.model_id, "model id"),
            (self.data_classification_ceiling, "model data ceiling"),
            (self.residency_boundary_id, "model residency boundary"),
            (self.telemetry_classification, "model telemetry classification"),
        ):
            validate_stable_identifier(value, label)
        if (
            self.provider_type != "provider-type.openai-compatible"
            or not 1024 <= self.context_limit <= 1_000_000
            or not 128 <= self.output_limit <= self.context_limit
            or not 1 <= self.timeout_seconds <= 300
            or not 0 <= self.max_retries <= 3
            or not 1 <= self.rate_limit_per_minute <= 10_000
            or not 1 <= self.concurrency_limit <= 128
            or not 1 <= len(self.approved_task_class_ids) <= 16
            or len(set(self.approved_task_class_ids)) != len(self.approved_task_class_ids)
        ):
            raise ValueError("model endpoint registration is outside platform bounds")
        for task_class_id in self.approved_task_class_ids:
            validate_stable_identifier(task_class_id, "model task class id")


@dataclass(frozen=True, slots=True)
class CoreIntegrationRegistration:
    integration_id: str
    integration_type: str
    owner_id: str
    purpose_id: str
    classification: str
    endpoint_reference_id: str
    trust_reference_id: str
    credential_reference_id: str | None
    scope_id: str
    rate_limit_per_minute: int
    validation_operation_id: str
    mapping_preview_id: str
    data_flow_id: str
    activation_state: IntegrationActivationState

    def __post_init__(self) -> None:
        for value, label in (
            (self.integration_id, "integration id"),
            (self.integration_type, "integration type"),
            (self.owner_id, "integration owner"),
            (self.purpose_id, "integration purpose"),
            (self.classification, "integration classification"),
            (self.endpoint_reference_id, "integration endpoint reference"),
            (self.trust_reference_id, "integration trust reference"),
            (self.scope_id, "integration scope"),
            (self.validation_operation_id, "integration validation operation"),
            (self.mapping_preview_id, "integration mapping preview"),
            (self.data_flow_id, "integration data flow"),
        ):
            validate_stable_identifier(value, label)
        if self.credential_reference_id is not None:
            validate_stable_identifier(
                self.credential_reference_id, "integration credential reference"
            )
        if (
            self.integration_type
            not in {
                "integration-type.model-gateway",
                "integration-type.enterprise-identity",
                "integration-type.security-export",
                "integration-type.storage-connector",
            }
            or self.activation_state is not IntegrationActivationState.INACTIVE
            or not 1 <= self.rate_limit_per_minute <= 10_000
            or not self.validation_operation_id.endswith(".read")
        ):
            raise ValueError("core integration registration is unsafe")


@dataclass(frozen=True, slots=True)
class IntegrationValidationCheck:
    check_id: str
    subject_id: str
    state: IntegrationCheckState
    result_code: str
    mandatory: bool

    def __post_init__(self) -> None:
        for value, label in (
            (self.check_id, "integration check id"),
            (self.subject_id, "integration check subject"),
            (self.result_code, "integration check result"),
        ):
            validate_stable_identifier(value, label)
        if self.mandatory and self.state is not IntegrationCheckState.PASSED:
            raise ValueError("mandatory integration validation must pass")


@dataclass(frozen=True, slots=True)
class BootstrapIntegrationPlan:
    schema_version: str
    release_id: str
    profile: DeploymentProfile
    organization_id: str
    environment_id: str
    site_id: str
    configuration_digest: str
    trust_plan_digest: str
    data_plan_digest: str
    service_plan_digest: str
    identity_plan_digest: str
    integration_plan_digest: str
    target_id: str
    target_kind: str
    target_state: IntegrationTargetState
    model_endpoint: ModelEndpointRegistration
    integrations: tuple[CoreIntegrationRegistration, ...]
    checks: tuple[IntegrationValidationCheck, ...]
    state: IntegrationPlanState
    result_code: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.schema_version != "atlas.bootstrap-integration-plan.v1":
            raise ValueError("bootstrap integration plan schema is unsupported")
        for value, label in (
            (self.release_id, "release id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.site_id, "site id"),
            (self.target_id, "integration target id"),
            (self.target_kind, "integration target kind"),
            (self.result_code, "integration plan result code"),
        ):
            validate_stable_identifier(value, label)
        if any(
            not SHA256_PATTERN.fullmatch(value)
            for value in (
                self.configuration_digest,
                self.trust_plan_digest,
                self.data_plan_digest,
                self.service_plan_digest,
                self.identity_plan_digest,
                self.integration_plan_digest,
            )
        ):
            raise ValueError("bootstrap integration plan digest is invalid")
        if (
            len(self.integrations) != 4
            or len(self.checks) != 12
            or self.generated_at.tzinfo is None
            or any(not item.mandatory for item in self.checks)
            or any(item.state is not IntegrationCheckState.PASSED for item in self.checks)
        ):
            raise ValueError("bootstrap integration plan evidence is incomplete")
        integration_ids = tuple(item.integration_id for item in self.integrations)
        check_ids = tuple(item.check_id for item in self.checks)
        if len(set(integration_ids)) != len(integration_ids) or len(set(check_ids)) != len(
            check_ids
        ):
            raise ValueError("bootstrap integration plan contains duplicate identities")


@dataclass(frozen=True, slots=True)
class IntegrationStateEvidence:
    evidence_id: str
    sha256: str
    size_bytes: int
    disposition: IntegrationStateDisposition

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_id, "integration evidence id")
        if not SHA256_PATTERN.fullmatch(self.sha256) or self.size_bytes < 1:
            raise ValueError("integration state evidence is invalid")


@dataclass(frozen=True, slots=True)
class IntegrationValidationExecution:
    execution_id: str
    phase_id: str
    release_id: str
    profile: DeploymentProfile
    configuration_digest: str
    trust_plan_digest: str
    data_plan_digest: str
    service_plan_digest: str
    identity_plan_digest: str
    integration_schema_version: str
    integration_plan_digest: str
    target_id: str
    state: IntegrationValidationState
    result_code: str
    started_at: datetime
    completed_at: datetime | None
    model_check_count: int
    integration_check_count: int
    mandatory_pass_count: int
    activation_count: int
    network_request_count: int
    secret_resolution_count: int
    checks: tuple[IntegrationValidationCheck, ...]
    evidence: tuple[IntegrationStateEvidence, ...]

    def __post_init__(self) -> None:
        for value, label in (
            (self.execution_id, "execution id"),
            (self.phase_id, "phase id"),
            (self.release_id, "release id"),
            (self.integration_schema_version, "integration schema version"),
            (self.target_id, "integration target id"),
            (self.result_code, "integration result code"),
        ):
            validate_stable_identifier(value, label)
        if (
            self.phase_id != "phase.integrations"
            or self.integration_schema_version != "atlas.bootstrap-integration-plan.v1"
        ):
            raise ValueError("integration validation phase identity is invalid")
        if any(
            not SHA256_PATTERN.fullmatch(value)
            for value in (
                self.configuration_digest,
                self.trust_plan_digest,
                self.data_plan_digest,
                self.service_plan_digest,
                self.identity_plan_digest,
                self.integration_plan_digest,
            )
        ):
            raise ValueError("integration validation digest is invalid")
        if self.started_at.tzinfo is None or (
            self.completed_at is not None and self.completed_at.tzinfo is None
        ):
            raise ValueError("integration validation timestamps must be timezone-aware")
        final_values = (
            self.model_check_count,
            self.integration_check_count,
            self.mandatory_pass_count,
            bool(self.checks),
            bool(self.evidence),
        )
        if self.activation_count or self.network_request_count or self.secret_resolution_count:
            raise ValueError("integration validation performed a forbidden operation")
        if self.state is IntegrationValidationState.RUNNING:
            if self.completed_at is not None or any(final_values):
                raise ValueError("running integration validation cannot contain final evidence")
        elif self.completed_at is None or self.completed_at < self.started_at:
            raise ValueError("finished integration validation requires a completion time")
        if self.state is IntegrationValidationState.COMPLETED:
            if (
                self.model_check_count != 8
                or self.integration_check_count != 4
                or self.mandatory_pass_count != 12
                or len(self.checks) != 12
                or any(item.state is not IntegrationCheckState.PASSED for item in self.checks)
                or len(self.evidence) != 1
            ):
                raise ValueError("completed integration validation evidence is incomplete")
        elif any(final_values):
            raise ValueError("failed integration validation cannot contain passed evidence")


@dataclass(frozen=True, slots=True)
class IntegrationValidationReceipt:
    checks: tuple[IntegrationValidationCheck, ...]
    evidence: tuple[IntegrationStateEvidence, ...]

    def __post_init__(self) -> None:
        if (
            len(self.checks) != 12
            or any(item.state is not IntegrationCheckState.PASSED for item in self.checks)
            or len(self.evidence) != 1
        ):
            raise ValueError("integration validation receipt is incomplete")
