"""ATLAS-033 SS4/SS6/SS7/SS8/SS9: telemetry separation, log categories, the canonical structured
log record, event naming, and log levels.

Lives in `atlas.core` alongside `audit.py` rather than under `atlas.modules/` -- logging is a
cross-cutting platform concern every module writes through, the same architectural placement this
session already established for `atlas.core.audit`. `LogSecurity.classification` reuses
`atlas.core.classification.DataClassification` directly rather than a parallel classification
scale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification

_EVENT_NAME_PATTERN = re.compile(r"^atlas(\.[a-z][a-z0-9_]*){1,}$")


class TelemetryType(StrEnum):
    """SS4's six telemetry types."""

    OPERATIONAL_LOG = "operational_log"
    SECURITY_LOG = "security_log"
    AUDIT_EVENT = "audit_event"
    METRIC = "metric"
    TRACE = "trace"
    EVIDENCE_ARTIFACT = "evidence_artifact"


def log_can_substitute_for_audit() -> bool:
    """SS4: "a single event may produce both a log and an audit event ... one must not be
    treated as a substitute for the other.\""""
    return False


class LogCategory(StrEnum):
    """SS6's twelve log categories. Category is independent of severity."""

    APPLICATION_LIFECYCLE_AND_CONFIGURATION = "application_lifecycle_and_configuration"
    API_AND_REQUEST_PROCESSING = "api_and_request_processing"
    AUTHENTICATION_AND_AUTHORIZATION_DIAGNOSTICS = "authentication_and_authorization_diagnostics"
    SECURITY_CONTROL_AND_ABUSE_SIGNALS = "security_control_and_abuse_signals"
    CONNECTOR_LIFECYCLE_COMMUNICATION_PARSING_AND_CAPABILITY_DIAGNOSTICS = (
        "connector_lifecycle_communication_parsing_and_capability_diagnostics"
    )
    WORKFLOW_SCHEDULING_TRANSITION_RETRY_AND_COMPENSATION_DIAGNOSTICS = (
        "workflow_scheduling_transition_retry_and_compensation_diagnostics"
    )
    AI_ORCHESTRATION_RETRIEVAL_TOOL_ROUTING_LATENCY_AND_REFUSAL_DIAGNOSTICS = (
        "ai_orchestration_retrieval_tool_routing_latency_and_refusal_diagnostics"
    )
    KNOWLEDGE_INGESTION_AND_INDEXING_DIAGNOSTICS = "knowledge_ingestion_and_indexing_diagnostics"
    EVENT_QUEUE_CACHE_DATABASE_AND_STORAGE_DIAGNOSTICS = (
        "event_queue_cache_database_and_storage_diagnostics"
    )
    INTEGRATION_DELIVERY_AND_ACKNOWLEDGEMENT_DIAGNOSTICS = (
        "integration_delivery_and_acknowledgement_diagnostics"
    )
    BACKUP_RESTORE_MIGRATION_BOOTSTRAP_AND_UPGRADE_DIAGNOSTICS = (
        "backup_restore_migration_bootstrap_and_upgrade_diagnostics"
    )
    PLATFORM_HEALTH_CAPACITY_AND_DEPENDENCY_DIAGNOSTICS = (
        "platform_health_capacity_and_dependency_diagnostics"
    )


class LogLevel(StrEnum):
    """SS9's six log levels, declared in ascending-severity order."""

    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


_LEVEL_SEVERITY: dict[LogLevel, int] = {level: index for index, level in enumerate(LogLevel)}


def is_at_least(level: LogLevel, *, threshold: LogLevel) -> bool:
    return _LEVEL_SEVERITY[level] >= _LEVEL_SEVERITY[threshold]


def is_valid_event_name(name: str) -> bool:
    """SS8: "event names use stable dotted identifiers such as `atlas.workflow.transition.
    failed`." Must start with the `atlas` namespace and at least one lowercase snake_case
    segment after it."""
    return bool(_EVENT_NAME_PATTERN.fullmatch(name))


def existing_event_meaning_can_be_changed_silently() -> bool:
    """SS8: "existing event meaning is not changed silently.\""""
    return False


def required_field_failure_silently_creates_a_malformed_record() -> bool:
    """SS8: "required-field failure is visible and does not silently create malformed
    records.\""""
    return False


@dataclass(frozen=True, slots=True)
class LogIdentity:
    """SS7's identity field group."""

    timestamp: datetime
    level: LogLevel
    event_name: str
    schema_version: str
    message: str

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if not is_valid_event_name(self.event_name):
            raise ValueError(f"{self.event_name!r} is not a valid stable dotted event name")
        if not self.schema_version.strip():
            raise ValueError("a log identity requires a schema version")
        if not self.message.strip():
            raise ValueError("a log identity requires a message")


@dataclass(frozen=True, slots=True)
class LogSource:
    """SS7's source field group."""

    service: str
    component: str
    instance: str
    version: str
    environment: str
    site: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("service", self.service),
            ("component", self.component),
            ("instance", self.instance),
            ("version", self.version),
            ("environment", self.environment),
            ("site", self.site),
        ):
            if not value.strip():
                raise ValueError(f"a log source requires {field_name}")


@dataclass(frozen=True, slots=True)
class LogCorrelation:
    """SS7's correlation field group. SS10: "correlation identifiers contain no customer data
    or secrets" is left to the caller minting them -- this type validates presence and shape,
    not content, since a correlation ID is an opaque identifier this type has no way to classify."""

    correlation_id: str
    request_id: str | None
    trace_id: str | None
    span_id: str | None
    session_or_workflow_run_reference: str | None

    def __post_init__(self) -> None:
        if not self.correlation_id.strip():
            raise ValueError("a log correlation requires a correlation id")


@dataclass(frozen=True, slots=True)
class LogContext:
    """SS7's context field group."""

    operation: str
    resource_type: str | None
    sanitized_target_reference: str | None
    connector_id: str | None
    capability_id: str | None

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise ValueError("a log context requires an operation")


@dataclass(frozen=True, slots=True)
class LogOutcome:
    """SS7's outcome field group."""

    status: str
    stable_error_code: str | None
    retryable: bool | None
    duration_ms: float | None
    attempt: int | None

    def __post_init__(self) -> None:
        if not self.status.strip():
            raise ValueError("a log outcome requires a status")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must not be negative")
        if self.attempt is not None and self.attempt < 1:
            raise ValueError("attempt must be a positive, 1-based attempt number")


@dataclass(frozen=True, slots=True)
class LogSecurity:
    """SS7's security field group."""

    classification: DataClassification
    redacted: bool
    security_category: str | None


@dataclass(frozen=True, slots=True)
class LogRuntime:
    """SS7's runtime field group -- every field is optional per SS7's own "where useful.\""""

    deployment: str | None
    node: str | None
    process: str | None
    thread_or_task_id: str | None


@dataclass(frozen=True, slots=True)
class StructuredLogRecord:
    """SS7: "each record includes" these seven field groups. Each group validates its own
    fields; there is no cross-group invariant beyond what each already enforces."""

    identity: LogIdentity
    source: LogSource
    correlation: LogCorrelation
    context: LogContext
    outcome: LogOutcome
    security: LogSecurity
    runtime: LogRuntime
