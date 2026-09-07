from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.classification import DataClassification
from atlas.core.structured_logging import (
    LogCategory,
    LogContext,
    LogCorrelation,
    LogIdentity,
    LogLevel,
    LogOutcome,
    LogRuntime,
    LogSecurity,
    LogSource,
    StructuredLogRecord,
    existing_event_meaning_can_be_changed_silently,
    is_at_least,
    is_valid_event_name,
    log_can_substitute_for_audit,
    required_field_failure_silently_creates_a_malformed_record,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def test_log_category_has_twelve_members() -> None:
    assert len(LogCategory) == 12


def test_log_level_has_six_members_in_ascending_order() -> None:
    assert list(LogLevel) == [
        LogLevel.TRACE,
        LogLevel.DEBUG,
        LogLevel.INFO,
        LogLevel.WARN,
        LogLevel.ERROR,
        LogLevel.CRITICAL,
    ]


def test_is_at_least_true_for_higher_or_equal_severity() -> None:
    assert is_at_least(LogLevel.ERROR, threshold=LogLevel.WARN) is True
    assert is_at_least(LogLevel.WARN, threshold=LogLevel.WARN) is True


def test_is_at_least_false_for_lower_severity() -> None:
    assert is_at_least(LogLevel.DEBUG, threshold=LogLevel.WARN) is False


@pytest.mark.parametrize(
    "name",
    [
        "atlas.workflow.transition.failed",
        "atlas.connector.request.timed_out",
        "atlas.auth.provider.unavailable",
    ],
)
def test_is_valid_event_name_accepts_documented_examples(name: str) -> None:
    assert is_valid_event_name(name) is True


@pytest.mark.parametrize("name", ["Atlas.workflow.failed", "workflow.failed", "atlas", ""])
def test_is_valid_event_name_rejects_malformed_names(name: str) -> None:
    assert is_valid_event_name(name) is False


def test_log_can_never_substitute_for_audit() -> None:
    assert log_can_substitute_for_audit() is False


def test_event_meaning_never_changed_silently() -> None:
    assert existing_event_meaning_can_be_changed_silently() is False


def test_required_field_failure_never_silently_creates_malformed_record() -> None:
    assert required_field_failure_silently_creates_a_malformed_record() is False


def identity(**overrides: object) -> LogIdentity:
    defaults: dict[str, object] = {
        "timestamp": NOW,
        "level": LogLevel.INFO,
        "event_name": "atlas.workflow.transition.completed",
        "schema_version": "1.0",
        "message": "Workflow run completed.",
    }
    defaults.update(overrides)
    return LogIdentity(**defaults)  # type: ignore[arg-type]


def test_identity_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        identity(timestamp=datetime(2026, 9, 4, 12, 0))


def test_identity_rejects_invalid_event_name() -> None:
    with pytest.raises(ValueError, match="not a valid stable dotted event name"):
        identity(event_name="not-a-valid-name")


def source() -> LogSource:
    return LogSource(
        service="atlas-backend",
        component="workflows",
        instance="atlas-backend-0",
        version="1.4.0",
        environment="production",
        site="site.primary",
    )


def test_source_requires_every_field() -> None:
    with pytest.raises(ValueError, match="requires component"):
        LogSource(
            service="atlas-backend",
            component="",
            instance="atlas-backend-0",
            version="1.4.0",
            environment="production",
            site="site.primary",
        )


def correlation() -> LogCorrelation:
    return LogCorrelation(
        correlation_id="correlation.example",
        request_id="request.example",
        trace_id=None,
        span_id=None,
        session_or_workflow_run_reference="workflow-run.example",
    )


def test_correlation_requires_correlation_id() -> None:
    with pytest.raises(ValueError, match="requires a correlation id"):
        LogCorrelation(
            correlation_id="",
            request_id=None,
            trace_id=None,
            span_id=None,
            session_or_workflow_run_reference=None,
        )


def context() -> LogContext:
    return LogContext(
        operation="workflow.transition",
        resource_type="workflow_run",
        sanitized_target_reference="target.controller-b",
        connector_id=None,
        capability_id=None,
    )


def test_context_requires_operation() -> None:
    with pytest.raises(ValueError, match="requires an operation"):
        LogContext(
            operation="",
            resource_type=None,
            sanitized_target_reference=None,
            connector_id=None,
            capability_id=None,
        )


def outcome() -> LogOutcome:
    return LogOutcome(
        status="completed", stable_error_code=None, retryable=None, duration_ms=120.0, attempt=1
    )


def test_outcome_rejects_negative_duration() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        LogOutcome(
            status="completed", stable_error_code=None, retryable=None, duration_ms=-1.0, attempt=1
        )


def test_outcome_rejects_non_positive_attempt() -> None:
    with pytest.raises(ValueError, match="positive, 1-based attempt"):
        LogOutcome(
            status="completed", stable_error_code=None, retryable=None, duration_ms=1.0, attempt=0
        )


def test_structured_log_record_accepts_valid_state() -> None:
    record = StructuredLogRecord(
        identity=identity(),
        source=source(),
        correlation=correlation(),
        context=context(),
        outcome=outcome(),
        security=LogSecurity(
            classification=DataClassification.INTERNAL, redacted=False, security_category=None
        ),
        runtime=LogRuntime(deployment=None, node=None, process=None, thread_or_task_id=None),
    )
    assert record.identity.level is LogLevel.INFO
