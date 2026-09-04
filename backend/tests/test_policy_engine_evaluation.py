from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atlas.core.capabilities import CapabilityClass
from atlas.modules.policy_engine.domain.evaluation import evaluate_policy
from atlas.modules.policy_engine.domain.models import (
    ConnectorTrustState,
    NonOverridableRule,
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

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64


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


def rule(
    *, rule_id: str, effect: PolicyDecisionOutcome, conditions: tuple[PolicyCondition, ...] = ()
) -> PolicyRule:
    return PolicyRule(rule_id=rule_id, effect=effect, conditions=conditions, summary=f"{rule_id}.")


def one_rule_set(*, set_id: str, layer: PolicySetLayer, rules: tuple[PolicyRule, ...]) -> PolicySet:
    return PolicySet(
        set_id=set_id,
        version=1,
        layer=layer,
        lifecycle_state=PolicyLifecycleState.ACTIVE,
        scope=PolicySetScope(),
        rule_document_digest=DIGEST,
        effective_from=NOW - timedelta(days=1),
        rules=rules,
    )


def test_a_non_overridable_violation_denies_before_any_policy_set_is_consulted() -> None:
    allow_everything = one_rule_set(
        set_id="policy-set.allow-all",
        layer=PolicySetLayer.PLATFORM,
        rules=(rule(rule_id="policy-rule.allow-all", effect=PolicyDecisionOutcome.ALLOW),),
    )
    decision = evaluate_policy(
        request(is_authenticated=False),
        (allow_everything,),
        decision_id="policy-decision.example",
        decided_at=NOW,
    )
    assert decision.outcome is PolicyDecisionOutcome.DENY
    assert decision.non_overridable_rule_references == (NonOverridableRule.UNAUTHENTICATED_ACCESS,)


def test_no_resolved_policy_sets_denies_by_default() -> None:
    decision = evaluate_policy(request(), (), decision_id="policy-decision.example", decided_at=NOW)
    assert decision.outcome is PolicyDecisionOutcome.DENY
    assert "denies by default" in decision.reasons[0].summary
    assert decision.non_overridable_rule_references == ()


def test_an_explicit_allow_rule_permits_the_operation() -> None:
    policy_set = one_rule_set(
        set_id="policy-set.example",
        layer=PolicySetLayer.PLATFORM,
        rules=(rule(rule_id="policy-rule.allow-c1", effect=PolicyDecisionOutcome.ALLOW),),
    )
    decision = evaluate_policy(
        request(), (policy_set,), decision_id="policy-decision.example", decided_at=NOW
    )
    assert decision.outcome is PolicyDecisionOutcome.ALLOW
    assert decision.reasons[0].policy_rule_reference == "policy-set.example:v1#policy-rule.allow-c1"
    assert decision.evaluated_policy_set_versions == ("policy-set.example:v1",)


def test_a_deny_rule_wins_over_an_allow_rule_regardless_of_order() -> None:
    policy_set = one_rule_set(
        set_id="policy-set.example",
        layer=PolicySetLayer.PLATFORM,
        rules=(
            rule(rule_id="policy-rule.allow", effect=PolicyDecisionOutcome.ALLOW),
            rule(rule_id="policy-rule.deny", effect=PolicyDecisionOutcome.DENY),
        ),
    )
    decision = evaluate_policy(
        request(), (policy_set,), decision_id="policy-decision.example", decided_at=NOW
    )
    assert decision.outcome is PolicyDecisionOutcome.DENY


def test_every_matching_deny_rule_is_recorded_not_just_the_first() -> None:
    policy_set = one_rule_set(
        set_id="policy-set.example",
        layer=PolicySetLayer.PLATFORM,
        rules=(
            rule(rule_id="policy-rule.deny-one", effect=PolicyDecisionOutcome.DENY),
            rule(rule_id="policy-rule.deny-two", effect=PolicyDecisionOutcome.DENY),
        ),
    )
    decision = evaluate_policy(
        request(), (policy_set,), decision_id="policy-decision.example", decided_at=NOW
    )
    assert len(decision.reasons) == 2


def test_a_deny_rule_wins_over_a_require_rule() -> None:
    policy_set = one_rule_set(
        set_id="policy-set.example",
        layer=PolicySetLayer.PLATFORM,
        rules=(
            rule(rule_id="policy-rule.require", effect=PolicyDecisionOutcome.REQUIRE_APPROVAL),
            rule(rule_id="policy-rule.deny", effect=PolicyDecisionOutcome.DENY),
        ),
    )
    decision = evaluate_policy(
        request(), (policy_set,), decision_id="policy-decision.example", decided_at=NOW
    )
    assert decision.outcome is PolicyDecisionOutcome.DENY
    assert decision.additional_conditions == ()


def test_multiple_require_outcomes_combine_into_a_primary_and_additional_conditions() -> None:
    policy_set = one_rule_set(
        set_id="policy-set.example",
        layer=PolicySetLayer.PLATFORM,
        rules=(
            rule(rule_id="policy-rule.approval", effect=PolicyDecisionOutcome.REQUIRE_APPROVAL),
            rule(
                rule_id="policy-rule.change-window",
                effect=PolicyDecisionOutcome.REQUIRE_CHANGE_WINDOW,
            ),
        ),
    )
    decision = evaluate_policy(
        request(), (policy_set,), decision_id="policy-decision.example", decided_at=NOW
    )
    # REQUIRE_CHANGE_WINDOW outranks REQUIRE_APPROVAL in this module's documented restrictiveness
    # ranking, so it is the primary outcome; REQUIRE_APPROVAL is not dropped, just demoted.
    assert decision.outcome is PolicyDecisionOutcome.REQUIRE_CHANGE_WINDOW
    assert decision.additional_conditions == (PolicyDecisionOutcome.REQUIRE_APPROVAL,)
    assert len(decision.reasons) == 2


def test_a_require_rule_wins_over_an_allow_rule() -> None:
    policy_set = one_rule_set(
        set_id="policy-set.example",
        layer=PolicySetLayer.PLATFORM,
        rules=(
            rule(rule_id="policy-rule.allow", effect=PolicyDecisionOutcome.ALLOW),
            rule(rule_id="policy-rule.require", effect=PolicyDecisionOutcome.REQUIRE_APPROVAL),
        ),
    )
    decision = evaluate_policy(
        request(), (policy_set,), decision_id="policy-decision.example", decided_at=NOW
    )
    assert decision.outcome is PolicyDecisionOutcome.REQUIRE_APPROVAL


def test_only_matching_rules_are_evaluated() -> None:
    policy_set = one_rule_set(
        set_id="policy-set.example",
        layer=PolicySetLayer.PLATFORM,
        rules=(
            rule(
                rule_id="policy-rule.deny-c5",
                effect=PolicyDecisionOutcome.DENY,
                conditions=(
                    PolicyCondition(
                        field=PolicyConditionField.CAPABILITY_CLASS,
                        operator=PolicyConditionOperator.EQUALS,
                        values=("C5",),
                    ),
                ),
            ),
            rule(rule_id="policy-rule.allow", effect=PolicyDecisionOutcome.ALLOW),
        ),
    )
    decision = evaluate_policy(
        request(capability_class=CapabilityClass.C1_READ_ONLY),
        (policy_set,),
        decision_id="policy-decision.example",
        decided_at=NOW,
    )
    assert decision.outcome is PolicyDecisionOutcome.ALLOW


def test_rules_from_multiple_resolved_sets_are_all_considered() -> None:
    platform_set = one_rule_set(
        set_id="policy-set.platform",
        layer=PolicySetLayer.PLATFORM,
        rules=(rule(rule_id="policy-rule.allow", effect=PolicyDecisionOutcome.ALLOW),),
    )
    org_set = one_rule_set(
        set_id="policy-set.org",
        layer=PolicySetLayer.ORGANIZATION,
        rules=(rule(rule_id="policy-rule.deny", effect=PolicyDecisionOutcome.DENY),),
    )
    decision = evaluate_policy(
        request(),
        (platform_set, org_set),
        decision_id="policy-decision.example",
        decided_at=NOW,
    )
    assert decision.outcome is PolicyDecisionOutcome.DENY
    assert set(decision.evaluated_policy_set_versions) == {
        "policy-set.platform:v1",
        "policy-set.org:v1",
    }
