"""ATLAS-021 SS18/SS19: logging/metrics/tracing and audit metadata.

`AuditMetadataSubmission` carries no field for actor, authorization, policy, or approval --
SS19: "the platform owns authoritative actor, authorization, policy, and approval references,"
enforced by absence, the same as SS12's `InvocationContext`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class TelemetryMetadata:
    """SS18: "the SDK automatically attaches" eight metadata fields."""

    component: str
    connector_id: str
    instance_reference: str
    capability_id: str
    invocation_id: str
    attempt: int
    correlation_id: str
    trace_id: str

    def __post_init__(self) -> None:
        if not self.component.strip():
            raise ValueError("telemetry metadata requires a component")
        validate_stable_identifier(self.connector_id, "connector_id")
        validate_stable_identifier(self.instance_reference, "instance_reference")
        validate_stable_identifier(self.capability_id, "capability_id")
        validate_stable_identifier(self.invocation_id, "invocation_id")
        if self.attempt < 1:
            raise ValueError("attempt must be a positive, 1-based attempt number")
        if not self.correlation_id.strip():
            raise ValueError("telemetry metadata requires a correlation id")
        if not self.trace_id.strip():
            raise ValueError("telemetry metadata requires a trace id")


class TelemetryRejectionReason(StrEnum):
    """SS18's five reject-or-redact categories."""

    SECRET_VALUES_OR_KNOWN_CREDENTIAL_OBJECTS = "secret_values_or_known_credential_objects"
    RAW_AUTHORIZATION_HEADERS = "raw_authorization_headers"
    UNBOUNDED_VENDOR_PAYLOADS = "unbounded_vendor_payloads"
    FULL_COMMAND_LINES_WITH_SENSITIVE_PARAMETERS = "full_command_lines_with_sensitive_parameters"
    USER_DOCUMENT_OR_PROMPT_CONTENT = "user_document_or_prompt_content"


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    """SS18: "connector authors provide event names and safe fields." Reuses Guardrails'
    `detect_secret_patterns` on every field value for the first of SS18's five rejection
    categories."""

    event_name: str
    safe_fields: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.event_name.strip():
            raise ValueError("a telemetry event requires a name")
        for _, value in self.safe_fields:
            if detect_secret_patterns(value):
                raise ValueError(
                    "SS18: the SDK rejects or redacts secret values and known credential objects"
                )


@dataclass(frozen=True, slots=True)
class MetricLabelConstraint:
    """SS18: "metric helpers constrain label names and cardinality.\""""

    allowed_label_names: frozenset[str]
    max_cardinality: int

    def __post_init__(self) -> None:
        if not self.allowed_label_names:
            raise ValueError("a metric label constraint requires at least one allowed label")
        if self.max_cardinality < 1:
            raise ValueError("max_cardinality must be positive")

    def is_allowed(self, label_name: str) -> bool:
        return label_name in self.allowed_label_names


def connector_handlers_write_directly_to_audit_store() -> bool:
    """SS19: "connector handlers do not write directly to the audit store. They return
    structured execution metadata to the runner and gateway.\""""
    return False


@dataclass(frozen=True, slots=True)
class AuditMetadataSubmission:
    """SS19's declared elements -- what a handler returns to the runner/gateway, not what it
    writes."""

    target_id: str
    capability_id: str
    evidence_references: tuple[str, ...]
    sanitized_parameter_summary: str
    vendor_operation_reference: str | None
    side_effect_confirmation: str | None
    outcome_confirmation: str
    source_observation_time: datetime
    partial_or_uncertain_outcome_detail: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.target_id, "target_id")
        validate_stable_identifier(self.capability_id, "capability_id")
        if not self.evidence_references:
            raise ValueError("an audit metadata submission requires evidence references")
        if not self.sanitized_parameter_summary.strip():
            raise ValueError("an audit metadata submission requires a parameter summary")
        if detect_secret_patterns(self.sanitized_parameter_summary):
            raise ValueError(
                "an audit metadata submission's parameter summary must not contain "
                "secret-looking content"
            )
        if not self.outcome_confirmation.strip():
            raise ValueError("an audit metadata submission requires an outcome confirmation")
        if self.source_observation_time.tzinfo is None:
            raise ValueError("source_observation_time must be timezone-aware")
