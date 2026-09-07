from __future__ import annotations

import pytest

from atlas.modules.observability.domain.correlation_content import (
    CausalityLink,
    ProhibitedLogContentKind,
    RedactionFailure,
    RedactionOutcome,
    RedactionRule,
    ScheduledWorkAttribution,
    SensitiveArtifactReference,
    debug_mode_can_disable_mandatory_redaction,
    scan_for_secret_content,
)


def test_causality_link_requires_parent_or_trace() -> None:
    with pytest.raises(ValueError, match="parent event id or trace context"):
        CausalityLink(parent_event_id=None, trace_context=None)


def test_causality_link_accepts_trace_context_alone() -> None:
    link = CausalityLink(parent_event_id=None, trace_context="trace.example")
    assert link.trace_context == "trace.example"


def test_scheduled_work_attribution_requires_accountable_owner() -> None:
    with pytest.raises(ValueError, match="requires an accountable owner"):
        ScheduledWorkAttribution(schedule_reference="schedule.nightly-backup", accountable_owner="")


def test_prohibited_log_content_kind_has_seven_members() -> None:
    assert len(ProhibitedLogContentKind) == 7


def test_scan_for_secret_content_true_for_aws_key() -> None:
    assert scan_for_secret_content("token=AKIAABCDEFGHIJKLMNOP") is True


def test_scan_for_secret_content_false_for_ordinary_text() -> None:
    assert scan_for_secret_content("Workflow run completed successfully.") is False


def test_sensitive_artifact_reference_validates_identifier() -> None:
    with pytest.raises(ValueError):
        SensitiveArtifactReference(evidence_store_reference="")


def test_redaction_rule_requires_positive_version() -> None:
    with pytest.raises(ValueError, match="requires a positive version"):
        RedactionRule(rule_id="redaction-rule.secret-names", version=0, covers="known secret names")


def test_redaction_outcome_requires_positive_rule_version() -> None:
    with pytest.raises(ValueError, match="requires a positive rule version"):
        RedactionOutcome(field_name="authorization", rule_version_applied=0, was_redacted=True)


def test_debug_mode_can_never_disable_mandatory_redaction() -> None:
    assert debug_mode_can_disable_mandatory_redaction() is False


def test_redaction_failure_requires_reason() -> None:
    with pytest.raises(ValueError, match="requires a reason"):
        RedactionFailure(record_reference="log-record.example", reason="", quarantined=True)
