from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.policy_engine.domain.break_glass import (
    BreakGlassOverrideError,
    BreakGlassRecord,
    apply_break_glass_override,
)
from atlas.modules.policy_engine.domain.models import (
    NonOverridableRule,
    PolicyDecision,
    PolicyDecisionOutcome,
    PolicyReason,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def record(**overrides: object) -> BreakGlassRecord:
    defaults: dict[str, object] = {
        "record_id": "break-glass-record.example",
        "identity_id": "subject.oncall-engineer",
        "authentication_method": "hardware-key-mfa",
        "justification": "Storage array unresponsive, customer-impacting outage in progress.",
        "incident_reference": "incident.example",
        "target_id": "target.example",
        "capability_class": CapabilityClass.C4_SERVICE_IMPACTING,
        "authorized_at": NOW,
        "duration": timedelta(minutes=30),
        "notified_identity_ids": ("subject.security-oncall",),
    }
    defaults.update(overrides)
    return BreakGlassRecord(**defaults)  # type: ignore[arg-type]


def deny_decision(
    *, non_overridable_rule_references: tuple[NonOverridableRule, ...] = ()
) -> PolicyDecision:
    return PolicyDecision(
        decision_id="policy-decision.example",
        decided_at=NOW,
        outcome=PolicyDecisionOutcome.DENY,
        reasons=(PolicyReason(summary="Denied by policy set."),),
        decision_request_id="policy-decision-request.example",
        correlation_id="correlation.example",
        actor_id="subject.oncall-engineer",
        operation_id="operation.example",
        non_overridable_rule_references=non_overridable_rule_references,
    )


def test_a_matching_active_record_overrides_a_policy_set_denial() -> None:
    overridden = apply_break_glass_override(
        deny_decision(),
        record(),
        target_id="target.example",
        capability_class=CapabilityClass.C4_SERVICE_IMPACTING,
        now=NOW,
        override_decision_id="policy-decision.override",
    )
    assert overridden.outcome is PolicyDecisionOutcome.ALLOW
    assert "break-glass-record.example" in overridden.reasons[0].summary


def test_cannot_override_a_non_overridable_denial() -> None:
    denial = deny_decision(
        non_overridable_rule_references=(NonOverridableRule.C5_AUTONOMOUS_EXECUTION,)
    )
    with pytest.raises(BreakGlassOverrideError, match="non-overridable"):
        apply_break_glass_override(
            denial,
            record(),
            target_id="target.example",
            capability_class=CapabilityClass.C4_SERVICE_IMPACTING,
            now=NOW,
            override_decision_id="policy-decision.override",
        )


def test_cannot_override_when_the_target_does_not_match() -> None:
    with pytest.raises(BreakGlassOverrideError, match="does not match"):
        apply_break_glass_override(
            deny_decision(),
            record(),
            target_id="target.other",
            capability_class=CapabilityClass.C4_SERVICE_IMPACTING,
            now=NOW,
            override_decision_id="policy-decision.override",
        )


def test_cannot_override_when_the_capability_class_does_not_match() -> None:
    with pytest.raises(BreakGlassOverrideError, match="does not match"):
        apply_break_glass_override(
            deny_decision(),
            record(),
            target_id="target.example",
            capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
            now=NOW,
            override_decision_id="policy-decision.override",
        )


def test_cannot_override_before_the_record_is_authorized() -> None:
    future_record = record(authorized_at=NOW + timedelta(minutes=5))
    with pytest.raises(BreakGlassOverrideError, match="not currently active"):
        apply_break_glass_override(
            deny_decision(),
            future_record,
            target_id="target.example",
            capability_class=CapabilityClass.C4_SERVICE_IMPACTING,
            now=NOW,
            override_decision_id="policy-decision.override",
        )


def test_cannot_override_after_the_record_expires() -> None:
    with pytest.raises(BreakGlassOverrideError, match="not currently active"):
        apply_break_glass_override(
            deny_decision(),
            record(),
            target_id="target.example",
            capability_class=CapabilityClass.C4_SERVICE_IMPACTING,
            now=NOW + timedelta(minutes=31),
            override_decision_id="policy-decision.override",
        )


def test_a_c5_break_glass_record_is_permitted_by_construction() -> None:
    # Break-glass structurally requires a named human + strong auth, so it can never represent
    # autonomous execution -- C5 itself is not banned, only the autonomous case (already caught
    # by the non-overridable check, tested above).
    c5_record = record(capability_class=CapabilityClass.C5_DESTRUCTIVE)
    assert c5_record.capability_class is CapabilityClass.C5_DESTRUCTIVE


def test_record_rejects_a_blank_justification() -> None:
    with pytest.raises(ValueError, match="justification"):
        record(justification="   ")


def test_record_rejects_a_blank_incident_reference() -> None:
    with pytest.raises(ValueError, match="incident or emergency record"):
        record(incident_reference="   ")


def test_record_rejects_a_non_positive_duration() -> None:
    with pytest.raises(ValueError, match="duration must be positive"):
        record(duration=timedelta(seconds=0))


def test_record_rejects_no_notified_identities() -> None:
    with pytest.raises(ValueError, match="independent notification"):
        record(notified_identity_ids=())


def test_is_active_at_boundary() -> None:
    example = record(authorized_at=NOW, duration=timedelta(minutes=10))
    assert example.is_active_at(NOW) is True
    assert example.is_active_at(NOW + timedelta(minutes=9, seconds=59)) is True
    assert example.is_active_at(NOW + timedelta(minutes=10)) is False
