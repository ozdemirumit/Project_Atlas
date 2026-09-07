from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from atlas.core.classification import DataClassification
from atlas.core.structured_logging import (
    LogContext,
    LogCorrelation,
    LogIdentity,
    LogLevel,
    LogOutcome,
    LogRuntime,
    LogSecurity,
    LogSource,
    StructuredLogRecord,
)
from atlas.modules.observability.application.log_sink import StandardLoggingSink

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def record(**overrides: object) -> StructuredLogRecord:
    defaults: dict[str, object] = {
        "identity": LogIdentity(
            timestamp=NOW,
            level=LogLevel.WARN,
            event_name="atlas.workflow.transition.retrying",
            schema_version="1.0",
            message="Workflow step retrying after transient failure.",
        ),
        "source": LogSource(
            service="atlas-backend",
            component="workflows",
            instance="atlas-backend-0",
            version="1.4.0",
            environment="production",
            site="site.primary",
        ),
        "correlation": LogCorrelation(
            correlation_id="correlation.example",
            request_id=None,
            trace_id=None,
            span_id=None,
            session_or_workflow_run_reference="workflow-run.example",
        ),
        "context": LogContext(
            operation="workflow.step.retry",
            resource_type="workflow_run",
            sanitized_target_reference=None,
            connector_id=None,
            capability_id=None,
        ),
        "outcome": LogOutcome(
            status="retrying", stable_error_code=None, retryable=True, duration_ms=50.0, attempt=2
        ),
        "security": LogSecurity(
            classification=DataClassification.INTERNAL, redacted=False, security_category=None
        ),
        "runtime": LogRuntime(deployment=None, node=None, process=None, thread_or_task_id=None),
    }
    defaults.update(overrides)
    return StructuredLogRecord(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_standard_logging_sink_emits_through_stdlib_logger() -> None:
    logger = logging.getLogger("test.atlas.observability.log_sink")
    captured: list[logging.LogRecord] = []

    class _CapturingHandler(logging.Handler):
        def emit(self, log_record: logging.LogRecord) -> None:
            captured.append(log_record)

    handler = _CapturingHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        sink = StandardLoggingSink(logger)
        await sink.emit(record())
    finally:
        logger.removeHandler(handler)

    assert len(captured) == 1
    emitted = captured[0]
    assert emitted.levelno == logging.WARNING
    assert emitted.getMessage() == "Workflow step retrying after transient failure."
    atlas_log = emitted.atlas_log  # type: ignore[attr-defined]
    assert atlas_log["identity"]["event_name"] == "atlas.workflow.transition.retrying"


@pytest.mark.asyncio
async def test_standard_logging_sink_maps_trace_below_debug() -> None:
    logger = logging.getLogger("test.atlas.observability.log_sink.trace")
    captured: list[logging.LogRecord] = []

    class _CapturingHandler(logging.Handler):
        def emit(self, log_record: logging.LogRecord) -> None:
            captured.append(log_record)

    handler = _CapturingHandler()
    logger.addHandler(handler)
    logger.setLevel(1)
    try:
        sink = StandardLoggingSink(logger)
        await sink.emit(
            record(
                identity=LogIdentity(
                    timestamp=NOW,
                    level=LogLevel.TRACE,
                    event_name="atlas.workflow.step.detail",
                    schema_version="1.0",
                    message="Very detailed temporary diagnosis.",
                )
            )
        )
    finally:
        logger.removeHandler(handler)

    assert len(captured) == 1
    assert captured[0].levelno == 5
    assert captured[0].levelno < logging.DEBUG
