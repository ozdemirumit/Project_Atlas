from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.policy_engine.domain.models import (
    ConnectorTrustState,
    PolicyApprovalStatus,
    PolicyDecisionOutcome,
    PolicyDecisionRequest,
)
from atlas.modules.policy_engine.domain.policy_set import (
    PolicyLifecycleState,
    PolicySet,
    PolicySetLayer,
    PolicySetScope,
)
from atlas.modules.policy_engine.domain.rule import (
    PolicyCondition,
    PolicyConditionField,
    PolicyConditionOperator,
    PolicyRule,
)
from atlas.modules.policy_engine.domain.simulation import (
    SimulationCase,
    find_outcome_regressions,
    simulate_policy,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
DIGEST = "d" * 64


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


def allow_all_policy_set(*, set_id: str = "policy-set.allow-all") -> PolicySet:
    return PolicySet(
        set_id=set_id,
        version=1,
        layer=PolicySetLayer.PLATFORM,
        lifecycle_state=PolicyLifecycleState.ACTIVE,
        scope=PolicySetScope(),
        rule_document_digest=DIGEST,
        effective_from=NOW - timedelta(days=1),
        rules=(
            PolicyRule(
                rule_id="policy-rule.allow-all",
                effect=PolicyDecisionOutcome.ALLOW,
                conditions=(),
                summary="Allow everything.",
            ),
        ),
    )


def deny_all_policy_set(*, set_id: str = "policy-set.deny-all") -> PolicySet:
    return PolicySet(
        set_id=set_id,
        version=1,
        layer=PolicySetLayer.PLATFORM,
        lifecycle_state=PolicyLifecycleState.ACTIVE,
        scope=PolicySetScope(),
        rule_document_digest=DIGEST,
        effective_from=NOW - timedelta(days=1),
        rules=(
            PolicyRule(
                rule_id="policy-rule.deny-all",
                effect=PolicyDecisionOutcome.DENY,
                conditions=(),
                summary="Deny everything.",
            ),
        ),
    )


def test_a_case_that_matches_its_expected_outcome_passes() -> None:
    case = SimulationCase(
        case_id="case.allow", request=request(), expected_outcome=PolicyDecisionOutcome.ALLOW
    )
    result = simulate_policy((case,), (allow_all_policy_set(),), decided_at=NOW)
    assert result.passed is True
    assert result.failures == ()


def test_a_case_that_does_not_match_its_expected_outcome_fails() -> None:
    case = SimulationCase(
        case_id="case.expected-allow-got-deny",
        request=request(),
        expected_outcome=PolicyDecisionOutcome.ALLOW,
    )
    result = simulate_policy((case,), (deny_all_policy_set(),), decided_at=NOW)
    assert result.passed is False
    assert len(result.failures) == 1
    assert result.failures[0].case_id == "case.expected-allow-got-deny"
    assert result.failures[0].actual_outcome is PolicyDecisionOutcome.DENY


def test_overall_result_fails_if_any_single_case_fails() -> None:
    passing = SimulationCase(
        case_id="case.pass", request=request(), expected_outcome=PolicyDecisionOutcome.ALLOW
    )
    failing = SimulationCase(
        case_id="case.fail",
        request=request(operation_id="operation.other"),
        expected_outcome=PolicyDecisionOutcome.DENY,
    )
    result = simulate_policy((passing, failing), (allow_all_policy_set(),), decided_at=NOW)
    assert result.passed is False
    assert len(result.failures) == 1
    assert result.failures[0].case_id == "case.fail"


def test_a_case_requires_a_non_empty_identifier() -> None:
    with pytest.raises(ValueError, match="requires an identifier"):
        SimulationCase(
            case_id="   ", request=request(), expected_outcome=PolicyDecisionOutcome.ALLOW
        )


def test_no_regressions_when_baseline_and_candidate_agree() -> None:
    case = SimulationCase(
        case_id="case.example", request=request(), expected_outcome=PolicyDecisionOutcome.ALLOW
    )
    changed = find_outcome_regressions(
        (case,),
        baseline_policy_sets=(allow_all_policy_set(),),
        candidate_policy_sets=(allow_all_policy_set(set_id="policy-set.allow-all-v2"),),
        decided_at=NOW,
    )
    assert changed == ()


def test_a_regression_is_reported_when_the_candidate_changes_the_outcome() -> None:
    case = SimulationCase(
        case_id="case.example", request=request(), expected_outcome=PolicyDecisionOutcome.ALLOW
    )
    changed = find_outcome_regressions(
        (case,),
        baseline_policy_sets=(allow_all_policy_set(),),
        candidate_policy_sets=(deny_all_policy_set(),),
        decided_at=NOW,
    )
    assert changed == ("case.example",)


def test_only_changed_cases_are_reported_not_unchanged_ones() -> None:
    stable_case = SimulationCase(
        case_id="case.stable",
        request=request(operation_id="operation.unaffected"),
        expected_outcome=PolicyDecisionOutcome.ALLOW,
    )
    changing_case = SimulationCase(
        case_id="case.changing", request=request(), expected_outcome=PolicyDecisionOutcome.ALLOW
    )
    baseline = allow_all_policy_set()
    candidate_rules = (
        PolicyRule(
            rule_id="policy-rule.deny-example",
            effect=PolicyDecisionOutcome.DENY,
            conditions=(
                PolicyCondition(
                    field=PolicyConditionField.OPERATION_ID,
                    operator=PolicyConditionOperator.EQUALS,
                    values=("operation.storage.health.read",),
                ),
            ),
            summary="Deny this specific operation only.",
        ),
        PolicyRule(
            rule_id="policy-rule.allow-rest",
            effect=PolicyDecisionOutcome.ALLOW,
            conditions=(),
            summary="Allow everything else.",
        ),
    )
    candidate = PolicySet(
        set_id="policy-set.candidate",
        version=1,
        layer=PolicySetLayer.PLATFORM,
        lifecycle_state=PolicyLifecycleState.ACTIVE,
        scope=PolicySetScope(),
        rule_document_digest=DIGEST,
        effective_from=NOW - timedelta(days=1),
        rules=candidate_rules,
    )
    changed = find_outcome_regressions(
        (stable_case, changing_case),
        baseline_policy_sets=(baseline,),
        candidate_policy_sets=(candidate,),
        decided_at=NOW,
    )
    assert changed == ("case.changing",)
