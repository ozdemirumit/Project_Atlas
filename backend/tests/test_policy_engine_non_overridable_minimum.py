from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.policy_engine.domain.models import (
    ConnectorTrustState,
    NonOverridableRule,
    PolicyApprovalStatus,
    PolicyDecision,
    PolicyDecisionOutcome,
    PolicyDecisionRequest,
    PolicyReason,
    evaluate_non_overridable_minimum,
    evaluate_policy_decision,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def clean_request(**overrides: object) -> PolicyDecisionRequest:
    defaults: dict[str, object] = {
        "decision_request_id": "policy-decision-request.example",
        "correlation_id": "correlation.example",
        "requested_at": NOW,
        "operation_id": "operation.storage.health.read",
        "is_authenticated": True,
        "is_authorized_for_scope": True,
        "actor_id": "subject.example",
        "actor_is_ai": False,
        "actor_organization_id": "organization.example",
        "actor_environment_id": "environment.production",
        "target_organization_id": "organization.example",
        "target_environment_id": "environment.production",
        "target_id": "target.example",
        "capability_class": CapabilityClass.C1_READ_ONLY,
        "connector_trust": ConnectorTrustState.TRUSTED,
        "approval_status": PolicyApprovalStatus.NOT_REQUIRED,
        "context_contains_secret": False,
        "operation_is_infrastructure_execution": False,
        "operation_is_approval": False,
        "execution_is_autonomous": False,
        "audit_required": False,
        "audit_persistence_available": True,
        "cross_boundary_explicitly_permitted": False,
    }
    defaults.update(overrides)
    return PolicyDecisionRequest(**defaults)  # type: ignore[arg-type]


def test_a_clean_request_violates_no_non_overridable_rule() -> None:
    assert evaluate_non_overridable_minimum(clean_request()) == ()


def test_a_clean_request_resolves_to_allow_with_no_reasons_or_rule_references() -> None:
    decision = evaluate_policy_decision(
        clean_request(), decision_id="policy-decision.example", decided_at=NOW
    )
    assert decision.outcome is PolicyDecisionOutcome.ALLOW
    assert decision.reasons == ()
    assert decision.non_overridable_rule_references == ()


def test_unauthenticated_access_is_denied() -> None:
    request = clean_request(is_authenticated=False)
    assert evaluate_non_overridable_minimum(request) == (NonOverridableRule.UNAUTHENTICATED_ACCESS,)


def test_unauthorized_scope_is_denied() -> None:
    request = clean_request(is_authorized_for_scope=False)
    assert evaluate_non_overridable_minimum(request) == (NonOverridableRule.UNAUTHORIZED_SCOPE,)


def test_unknown_capability_class_is_denied() -> None:
    request = clean_request(capability_class=None)
    assert evaluate_non_overridable_minimum(request) == (
        NonOverridableRule.UNKNOWN_CAPABILITY_CLASS,
    )


@pytest.mark.parametrize(
    "trust_state",
    [
        ConnectorTrustState.DISABLED,
        ConnectorTrustState.SUSPENDED,
        ConnectorTrustState.UNTRUSTED,
        ConnectorTrustState.INCOMPATIBLE,
    ],
)
def test_a_non_trusted_connector_is_denied(trust_state: ConnectorTrustState) -> None:
    request = clean_request(connector_trust=trust_state)
    assert evaluate_non_overridable_minimum(request) == (NonOverridableRule.UNTRUSTED_CONNECTOR,)


@pytest.mark.parametrize(
    "approval_status",
    [PolicyApprovalStatus.EXPIRED, PolicyApprovalStatus.MISMATCHED],
)
def test_an_expired_or_mismatched_approval_is_denied(
    approval_status: PolicyApprovalStatus,
) -> None:
    request = clean_request(approval_status=approval_status)
    assert evaluate_non_overridable_minimum(request) == (NonOverridableRule.INVALID_APPROVAL,)


@pytest.mark.parametrize(
    "approval_status",
    [PolicyApprovalStatus.NOT_REQUIRED, PolicyApprovalStatus.NOT_PROVIDED],
)
def test_a_missing_or_not_required_approval_does_not_violate_invalid_approval(
    approval_status: PolicyApprovalStatus,
) -> None:
    request = clean_request(approval_status=approval_status)
    assert evaluate_non_overridable_minimum(request) == ()


def test_a_secret_in_context_is_denied() -> None:
    request = clean_request(context_contains_secret=True)
    assert evaluate_non_overridable_minimum(request) == (NonOverridableRule.SECRET_IN_CONTEXT,)


def test_autonomous_c5_execution_is_denied() -> None:
    request = clean_request(
        capability_class=CapabilityClass.C5_DESTRUCTIVE, execution_is_autonomous=True
    )
    assert evaluate_non_overridable_minimum(request) == (
        NonOverridableRule.C5_AUTONOMOUS_EXECUTION,
    )


def test_human_initiated_c5_execution_does_not_violate_the_autonomous_rule() -> None:
    request = clean_request(
        capability_class=CapabilityClass.C5_DESTRUCTIVE, execution_is_autonomous=False
    )
    assert evaluate_non_overridable_minimum(request) == ()


@pytest.mark.parametrize(
    "overrides",
    [
        {"operation_is_approval": True},
        {"operation_is_infrastructure_execution": True},
    ],
)
def test_an_ai_actor_cannot_approve_or_execute_infrastructure(
    overrides: dict[str, object],
) -> None:
    request = clean_request(actor_is_ai=True, **overrides)
    assert evaluate_non_overridable_minimum(request) == (
        NonOverridableRule.AI_APPROVAL_OR_EXECUTION,
    )


def test_a_human_actor_may_approve_and_execute() -> None:
    request = clean_request(
        actor_is_ai=False,
        operation_is_approval=True,
        operation_is_infrastructure_execution=True,
    )
    assert evaluate_non_overridable_minimum(request) == ()


def test_audit_required_but_unavailable_is_denied() -> None:
    request = clean_request(audit_required=True, audit_persistence_available=False)
    assert evaluate_non_overridable_minimum(request) == (NonOverridableRule.AUDIT_UNAVAILABLE,)


def test_audit_unavailable_does_not_matter_when_audit_is_not_required() -> None:
    request = clean_request(audit_required=False, audit_persistence_available=False)
    assert evaluate_non_overridable_minimum(request) == ()


@pytest.mark.parametrize(
    "overrides",
    [
        {"target_organization_id": "organization.other"},
        {"target_environment_id": "environment.staging"},
    ],
)
def test_a_cross_boundary_request_is_denied_without_explicit_permission(
    overrides: dict[str, object],
) -> None:
    request = clean_request(cross_boundary_explicitly_permitted=False, **overrides)
    assert request.crosses_organization_or_environment_boundary is True
    assert evaluate_non_overridable_minimum(request) == (NonOverridableRule.CROSS_BOUNDARY_ACCESS,)


def test_a_cross_boundary_request_is_allowed_through_this_rule_when_explicitly_permitted() -> None:
    request = clean_request(
        target_organization_id="organization.other",
        cross_boundary_explicitly_permitted=True,
    )
    assert evaluate_non_overridable_minimum(request) == ()


def test_multiple_simultaneous_violations_are_all_reported_in_rule_order() -> None:
    request = clean_request(is_authenticated=False, context_contains_secret=True)
    violations = evaluate_non_overridable_minimum(request)
    assert violations == (
        NonOverridableRule.UNAUTHENTICATED_ACCESS,
        NonOverridableRule.SECRET_IN_CONTEXT,
    )


def test_a_violating_request_resolves_to_deny_with_a_reason_per_violation() -> None:
    request = clean_request(is_authenticated=False, context_contains_secret=True)
    decision = evaluate_policy_decision(
        request, decision_id="policy-decision.example", decided_at=NOW
    )
    assert decision.outcome is PolicyDecisionOutcome.DENY
    assert len(decision.reasons) == 2
    assert decision.non_overridable_rule_references == (
        NonOverridableRule.UNAUTHENTICATED_ACCESS,
        NonOverridableRule.SECRET_IN_CONTEXT,
    )
    assert all(reason.summary.strip() for reason in decision.reasons)


def test_request_rejects_a_naive_requested_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        clean_request(requested_at=datetime(2026, 9, 4, 12, 0))


def test_request_rejects_an_unstable_identifier() -> None:
    with pytest.raises(ValueError):
        clean_request(actor_id="")


def test_decision_rejects_a_deny_outcome_with_no_reasons() -> None:
    with pytest.raises(ValueError, match="requires at least one reason"):
        PolicyDecision(
            decision_id="policy-decision.example",
            decided_at=NOW,
            outcome=PolicyDecisionOutcome.DENY,
            reasons=(),
            decision_request_id="policy-decision-request.example",
            correlation_id="correlation.example",
            actor_id="subject.example",
            operation_id="operation.example",
            non_overridable_rule_references=(),
        )


def test_decision_rejects_an_allow_outcome_carrying_rule_references() -> None:
    with pytest.raises(ValueError, match="cannot carry non-overridable rule references"):
        PolicyDecision(
            decision_id="policy-decision.example",
            decided_at=NOW,
            outcome=PolicyDecisionOutcome.ALLOW,
            reasons=(),
            decision_request_id="policy-decision-request.example",
            correlation_id="correlation.example",
            actor_id="subject.example",
            operation_id="operation.example",
            non_overridable_rule_references=(NonOverridableRule.SECRET_IN_CONTEXT,),
        )


def test_reason_rejects_a_blank_summary() -> None:
    with pytest.raises(ValueError, match="requires a summary"):
        PolicyReason(non_overridable_rule=NonOverridableRule.SECRET_IN_CONTEXT, summary="   ")


def test_reason_rejects_both_a_non_overridable_rule_and_a_policy_rule_reference() -> None:
    with pytest.raises(ValueError, match="cannot reference both"):
        PolicyReason(
            summary="Example.",
            non_overridable_rule=NonOverridableRule.SECRET_IN_CONTEXT,
            policy_rule_reference="policy-set.example:v1#policy-rule.example",
        )


def test_decision_rejects_additional_conditions_on_an_allow_outcome() -> None:
    with pytest.raises(ValueError, match="only a REQUIRE_\\* outcome"):
        PolicyDecision(
            decision_id="policy-decision.example",
            decided_at=NOW,
            outcome=PolicyDecisionOutcome.ALLOW,
            reasons=(PolicyReason(summary="Example."),),
            decision_request_id="policy-decision-request.example",
            correlation_id="correlation.example",
            actor_id="subject.example",
            operation_id="operation.example",
            non_overridable_rule_references=(),
            additional_conditions=(PolicyDecisionOutcome.REQUIRE_APPROVAL,),
        )


def test_decision_rejects_the_primary_outcome_repeated_in_additional_conditions() -> None:
    with pytest.raises(ValueError, match="must not repeat"):
        PolicyDecision(
            decision_id="policy-decision.example",
            decided_at=NOW,
            outcome=PolicyDecisionOutcome.REQUIRE_APPROVAL,
            reasons=(PolicyReason(summary="Example."),),
            decision_request_id="policy-decision-request.example",
            correlation_id="correlation.example",
            actor_id="subject.example",
            operation_id="operation.example",
            non_overridable_rule_references=(),
            additional_conditions=(PolicyDecisionOutcome.REQUIRE_APPROVAL,),
        )


def test_decision_rejects_a_duplicated_additional_condition() -> None:
    with pytest.raises(ValueError, match="must not repeat an outcome"):
        PolicyDecision(
            decision_id="policy-decision.example",
            decided_at=NOW,
            outcome=PolicyDecisionOutcome.REQUIRE_CHANGE_WINDOW,
            reasons=(PolicyReason(summary="Example."),),
            decision_request_id="policy-decision-request.example",
            correlation_id="correlation.example",
            actor_id="subject.example",
            operation_id="operation.example",
            non_overridable_rule_references=(),
            additional_conditions=(
                PolicyDecisionOutcome.REQUIRE_APPROVAL,
                PolicyDecisionOutcome.REQUIRE_APPROVAL,
            ),
        )


def test_outcome_allowed_property_is_true_only_for_allow() -> None:
    for outcome in PolicyDecisionOutcome:
        assert outcome.allowed == (outcome is PolicyDecisionOutcome.ALLOW)


def test_replace_helper_still_produces_a_valid_request() -> None:
    base = clean_request()
    changed = replace(base, actor_is_ai=True)
    assert changed.actor_is_ai is True
    assert evaluate_non_overridable_minimum(changed) == ()
