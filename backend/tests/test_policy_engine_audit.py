from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.policy_engine.application.audit import record_policy_decision
from atlas.modules.policy_engine.domain.models import (
    NonOverridableRule,
    PolicyDecision,
    PolicyDecisionOutcome,
    PolicyReason,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


class RecordingAuditSink:
    def __init__(self) -> None:
        self.recorded: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.recorded.append(event)


def decision(
    *,
    outcome: PolicyDecisionOutcome,
    reasons: tuple[PolicyReason, ...] = (),
    non_overridable_rule_references: tuple[NonOverridableRule, ...] = (),
) -> PolicyDecision:
    return PolicyDecision(
        decision_id="policy-decision.example",
        decided_at=NOW,
        outcome=outcome,
        reasons=reasons,
        decision_request_id="policy-decision-request.example",
        correlation_id="correlation.example",
        actor_id="subject.example",
        operation_id="operation.example",
        non_overridable_rule_references=non_overridable_rule_references,
    )


@pytest.mark.asyncio
async def test_an_allow_decision_is_recorded_with_the_allow_result_code() -> None:
    sink = RecordingAuditSink()
    await record_policy_decision(
        sink,
        decision(outcome=PolicyDecisionOutcome.ALLOW),
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    assert len(sink.recorded) == 1
    event = sink.recorded[0]
    assert event.event_type == "atlas.policy_engine.decision.allow"
    assert event.result_code == "policy.allowed"
    assert event.outcome == "allow"
    assert event.decision_id == "policy-decision.example"
    assert event.correlation_id == "correlation.example"
    assert event.subject_id == "subject.example"


@pytest.mark.asyncio
async def test_a_non_overridable_denial_uses_its_own_result_code() -> None:
    sink = RecordingAuditSink()
    reason = PolicyReason(
        non_overridable_rule=NonOverridableRule.SECRET_IN_CONTEXT, summary="Example."
    )
    await record_policy_decision(
        sink,
        decision(
            outcome=PolicyDecisionOutcome.DENY,
            reasons=(reason,),
            non_overridable_rule_references=(NonOverridableRule.SECRET_IN_CONTEXT,),
        ),
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    assert sink.recorded[0].result_code == "policy.non_overridable_denied"


@pytest.mark.asyncio
async def test_a_rule_driven_denial_uses_the_rule_denied_result_code() -> None:
    sink = RecordingAuditSink()
    reason = PolicyReason(
        policy_rule_reference="policy-set.example:v1#policy-rule.example", summary="Example."
    )
    await record_policy_decision(
        sink,
        decision(outcome=PolicyDecisionOutcome.DENY, reasons=(reason,)),
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    assert sink.recorded[0].result_code == "policy.rule_denied"


@pytest.mark.asyncio
async def test_a_deny_by_default_denial_uses_its_own_result_code() -> None:
    sink = RecordingAuditSink()
    reason = PolicyReason(summary="No policy rule grants this operation.")
    await record_policy_decision(
        sink,
        decision(outcome=PolicyDecisionOutcome.DENY, reasons=(reason,)),
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    assert sink.recorded[0].result_code == "policy.deny_by_default"


@pytest.mark.asyncio
async def test_a_require_outcome_uses_the_condition_required_result_code() -> None:
    sink = RecordingAuditSink()
    await record_policy_decision(
        sink,
        decision(outcome=PolicyDecisionOutcome.REQUIRE_APPROVAL),
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    assert sink.recorded[0].result_code == "policy.condition_required"


@pytest.mark.asyncio
async def test_reason_field_carries_the_first_reasons_summary() -> None:
    sink = RecordingAuditSink()
    reason = PolicyReason(summary="First reason.")
    second_reason = PolicyReason(summary="Second reason.")
    await record_policy_decision(
        sink,
        decision(outcome=PolicyDecisionOutcome.DENY, reasons=(reason, second_reason)),
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    assert sink.recorded[0].reason == "First reason."


@pytest.mark.asyncio
async def test_an_allow_decision_with_no_reasons_has_no_reason_field() -> None:
    sink = RecordingAuditSink()
    await record_policy_decision(
        sink,
        decision(outcome=PolicyDecisionOutcome.ALLOW),
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    assert sink.recorded[0].reason is None
