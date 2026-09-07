from __future__ import annotations

import pytest

from atlas.modules.observability.domain.failure_observability import (
    LoggingPipelineMetric,
    QuarantinedRecord,
    buffer_saturation_drops_highest_priority_records_first,
    logging_failure_changes_unknown_result_to_success,
    mandatory_audit_failure_follows_the_more_permissive_log_behavior,
)


def test_buffer_saturation_never_drops_highest_priority_first() -> None:
    assert buffer_saturation_drops_highest_priority_records_first() is False


def test_quarantined_record_requires_safe_diagnostic() -> None:
    with pytest.raises(ValueError, match="requires a safe producer diagnostic"):
        QuarantinedRecord(record_reference="log-record.example", safe_producer_diagnostic="")


def test_logging_failure_never_changes_unknown_result_to_success() -> None:
    assert logging_failure_changes_unknown_result_to_success() is False


def test_mandatory_audit_failure_never_follows_permissive_log_behavior() -> None:
    assert mandatory_audit_failure_follows_the_more_permissive_log_behavior() is False


def test_logging_pipeline_metric_has_eight_members() -> None:
    assert len(LoggingPipelineMetric) == 8
