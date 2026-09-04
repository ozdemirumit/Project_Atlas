from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.policy_engine.domain.models import (
    ConnectorTrustState,
    PolicyApprovalStatus,
    PolicyDecisionOutcome,
    PolicyDecisionRequest,
)
from atlas.modules.policy_engine.domain.rule import (
    PolicyCondition,
    PolicyConditionField,
    PolicyConditionOperator,
    PolicyRule,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def request(**overrides: object) -> PolicyDecisionRequest:
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


def test_equals_condition_matches_the_exact_value() -> None:
    condition = PolicyCondition(
        field=PolicyConditionField.OPERATION_ID,
        operator=PolicyConditionOperator.EQUALS,
        values=("operation.storage.health.read",),
    )
    assert condition.matches(request()) is True
    assert condition.matches(request(operation_id="operation.other")) is False


def test_not_equals_condition() -> None:
    condition = PolicyCondition(
        field=PolicyConditionField.OPERATION_ID,
        operator=PolicyConditionOperator.NOT_EQUALS,
        values=("operation.other",),
    )
    assert condition.matches(request()) is True
    assert condition.matches(request(operation_id="operation.other")) is False


def test_in_condition() -> None:
    condition = PolicyCondition(
        field=PolicyConditionField.CAPABILITY_CLASS,
        operator=PolicyConditionOperator.IN,
        values=("C0", "C1"),
    )
    assert condition.matches(request(capability_class=CapabilityClass.C1_READ_ONLY)) is True
    assert (
        condition.matches(request(capability_class=CapabilityClass.C4_SERVICE_IMPACTING)) is False
    )


def test_not_in_condition() -> None:
    condition = PolicyCondition(
        field=PolicyConditionField.CAPABILITY_CLASS,
        operator=PolicyConditionOperator.NOT_IN,
        values=("C4", "C5"),
    )
    assert condition.matches(request(capability_class=CapabilityClass.C1_READ_ONLY)) is True
    assert condition.matches(request(capability_class=CapabilityClass.C5_DESTRUCTIVE)) is False


def test_capability_class_field_reads_none_as_an_empty_string() -> None:
    condition = PolicyCondition(
        field=PolicyConditionField.CAPABILITY_CLASS,
        operator=PolicyConditionOperator.EQUALS,
        values=("",),
    )
    assert condition.matches(request(capability_class=None)) is True


def test_boolean_field_is_compared_as_true_or_false_strings() -> None:
    condition = PolicyCondition(
        field=PolicyConditionField.ACTOR_IS_AI,
        operator=PolicyConditionOperator.EQUALS,
        values=("true",),
    )
    assert condition.matches(request(actor_is_ai=True)) is True
    assert condition.matches(request(actor_is_ai=False)) is False


def test_enum_fields_compare_against_their_string_value() -> None:
    trust_condition = PolicyCondition(
        field=PolicyConditionField.CONNECTOR_TRUST,
        operator=PolicyConditionOperator.EQUALS,
        values=("trusted",),
    )
    assert trust_condition.matches(request()) is True
    approval_condition = PolicyCondition(
        field=PolicyConditionField.APPROVAL_STATUS,
        operator=PolicyConditionOperator.EQUALS,
        values=("not_required",),
    )
    assert approval_condition.matches(request()) is True


def test_condition_requires_at_least_one_value() -> None:
    with pytest.raises(ValueError, match="at least one value"):
        PolicyCondition(
            field=PolicyConditionField.OPERATION_ID,
            operator=PolicyConditionOperator.IN,
            values=(),
        )


def test_equals_condition_rejects_more_than_one_value() -> None:
    with pytest.raises(ValueError, match="exactly one value"):
        PolicyCondition(
            field=PolicyConditionField.OPERATION_ID,
            operator=PolicyConditionOperator.EQUALS,
            values=("a", "b"),
        )


def test_a_rule_with_no_conditions_matches_every_request() -> None:
    rule = PolicyRule(
        rule_id="policy-rule.catch-all-deny",
        effect=PolicyDecisionOutcome.DENY,
        conditions=(),
        summary="Deny everything not explicitly allowed.",
    )
    assert rule.matches(request()) is True
    assert rule.matches(request(operation_id="operation.anything.else")) is True


def test_a_rule_combines_its_conditions_with_and() -> None:
    rule = PolicyRule(
        rule_id="policy-rule.c1-read-only-allow",
        effect=PolicyDecisionOutcome.ALLOW,
        conditions=(
            PolicyCondition(
                field=PolicyConditionField.CAPABILITY_CLASS,
                operator=PolicyConditionOperator.EQUALS,
                values=("C1",),
            ),
            PolicyCondition(
                field=PolicyConditionField.CONNECTOR_TRUST,
                operator=PolicyConditionOperator.EQUALS,
                values=("trusted",),
            ),
        ),
        summary="Allow trusted C1 reads.",
    )
    assert rule.matches(request()) is True
    assert rule.matches(request(capability_class=CapabilityClass.C4_SERVICE_IMPACTING)) is False
    assert rule.matches(request(connector_trust=ConnectorTrustState.UNTRUSTED)) is False


def test_rule_rejects_a_blank_summary() -> None:
    with pytest.raises(ValueError, match="requires a summary"):
        PolicyRule(
            rule_id="policy-rule.example",
            effect=PolicyDecisionOutcome.ALLOW,
            conditions=(),
            summary="   ",
        )


def test_rule_rejects_an_unstable_identifier() -> None:
    with pytest.raises(ValueError):
        PolicyRule(
            rule_id="",
            effect=PolicyDecisionOutcome.ALLOW,
            conditions=(),
            summary="Example.",
        )
