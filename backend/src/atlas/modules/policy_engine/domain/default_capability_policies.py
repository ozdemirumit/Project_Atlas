"""ATLAS-025 SS11: the default capability-class posture table, wired as a real Platform-layer
PolicySet rather than special-cased logic -- SS9's precedence combination (deny wins, conditions
combine, explicit allow) then applies to it exactly the same as any other resolved set, and a
more specific layer (organization, environment, connector, ...) can still add stricter or
additional rules on top of it.

SS11's six rows describe richer conditions than this slice's rule vocabulary can express yet --
"approved target", "full audit", "resource and service impact", "current impact analysis",
"change record", "change window", and "recovery plan" are none of them evaluable fields today.
Each rule below is the closest faithful approximation using only what
`policy_engine.domain.rule.PolicyConditionField` currently exposes, and says exactly what it does
not yet enforce in its own summary -- nothing here overclaims SS11's full text.
"""

from __future__ import annotations

from datetime import datetime

from atlas.modules.policy_engine.domain.models import PolicyDecisionOutcome
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
    compute_rule_document_digest,
)

DEFAULT_CAPABILITY_POLICY_SET_ID = "policy-set.platform-default-capability-matrix"


def _capability_equals(value: str) -> PolicyCondition:
    return PolicyCondition(
        field=PolicyConditionField.CAPABILITY_CLASS,
        operator=PolicyConditionOperator.EQUALS,
        values=(value,),
    )


def _approval_equals(value: str) -> PolicyCondition:
    return PolicyCondition(
        field=PolicyConditionField.APPROVAL_STATUS,
        operator=PolicyConditionOperator.EQUALS,
        values=(value,),
    )


def _approval_not_equals(value: str) -> PolicyCondition:
    return PolicyCondition(
        field=PolicyConditionField.APPROVAL_STATUS,
        operator=PolicyConditionOperator.NOT_EQUALS,
        values=(value,),
    )


DEFAULT_CAPABILITY_RULES: tuple[PolicyRule, ...] = (
    PolicyRule(
        rule_id="policy-rule.default-c0-allow",
        effect=PolicyDecisionOutcome.ALLOW,
        conditions=(_capability_equals("C0"),),
        summary=(
            "C0 is allowed by default within authorized data scope (SS11); scope authorization"
            " itself is the non-overridable UNAUTHORIZED_SCOPE rule, evaluated before any policy"
            " set is even consulted."
        ),
    ),
    PolicyRule(
        rule_id="policy-rule.default-c1-allow-trusted-connector",
        effect=PolicyDecisionOutcome.ALLOW,
        conditions=(
            _capability_equals("C1"),
            PolicyCondition(
                field=PolicyConditionField.CONNECTOR_TRUST,
                operator=PolicyConditionOperator.EQUALS,
                values=("trusted",),
            ),
        ),
        summary=(
            "C1 is allowed by default for an authorized identity through a healthy, trusted"
            " connector (SS11). Target-approval and audit-completeness are not yet evaluable"
            " fields and are not enforced by this rule."
        ),
    ),
    PolicyRule(
        rule_id="policy-rule.default-c2-require-evidence",
        effect=PolicyDecisionOutcome.REQUIRE_ADDITIONAL_EVIDENCE,
        conditions=(_capability_equals("C2"),),
        summary=(
            "C2 requires policy-defined evidence or approval by default (SS11); this rule always"
            " requires evidence rather than varying by resource/service impact, which is not yet"
            " an evaluable field."
        ),
    ),
    PolicyRule(
        rule_id="policy-rule.default-c3-allow-with-valid-approval",
        effect=PolicyDecisionOutcome.ALLOW,
        conditions=(_capability_equals("C3"), _approval_equals("valid")),
        summary="C3 is allowed once explicitly enabled with an exact, valid approval (SS11).",
    ),
    PolicyRule(
        rule_id="policy-rule.default-c3-deny-without-approval",
        effect=PolicyDecisionOutcome.DENY,
        conditions=(_capability_equals("C3"), _approval_not_equals("valid")),
        summary=(
            "C3 is denied by default without an exact, valid approval (SS11). Deterministic"
            " execution controls beyond approval are not yet evaluable and are not enforced by"
            " this rule."
        ),
    ),
    PolicyRule(
        rule_id="policy-rule.default-c4-allow-with-valid-approval",
        effect=PolicyDecisionOutcome.ALLOW,
        conditions=(_capability_equals("C4"), _approval_equals("valid")),
        summary=(
            "C4 is allowed by default once a valid, matching approval is present (SS11)."
            " Current impact analysis, change record, change window, and recovery-plan validity"
            " are not yet evaluable fields -- only the approval condition is enforced by this"
            " rule."
        ),
    ),
    PolicyRule(
        rule_id="policy-rule.default-c4-deny-without-approval",
        effect=PolicyDecisionOutcome.DENY,
        conditions=(_capability_equals("C4"), _approval_not_equals("valid")),
        summary="C4 is denied by default without privileged approval (SS11).",
    ),
    PolicyRule(
        rule_id="policy-rule.default-c5-require-manual-execution",
        effect=PolicyDecisionOutcome.REQUIRE_MANUAL_EXECUTION,
        conditions=(_capability_equals("C5"),),
        summary=(
            "C5 permits only an exceptional, human-governed procedure by default (SS11) --"
            " modeled as the strictest REQUIRE_* outcome available. Autonomous C5 execution is"
            " already denied outright by the non-overridable C5_AUTONOMOUS_EXECUTION rule before"
            " this is ever reached."
        ),
    ),
)


def default_capability_policy_set(*, effective_from: datetime) -> PolicySet:
    """Builds SS11's default capability-class posture table as one real, ACTIVE, Platform-layer
    PolicySet with an empty (universal) scope. Callers seed it into their PolicySetRepository at
    bootstrap; nothing here is special-cased in the evaluator."""
    return PolicySet(
        set_id=DEFAULT_CAPABILITY_POLICY_SET_ID,
        version=1,
        layer=PolicySetLayer.PLATFORM,
        lifecycle_state=PolicyLifecycleState.ACTIVE,
        scope=PolicySetScope(),
        rule_document_digest=compute_rule_document_digest(DEFAULT_CAPABILITY_RULES),
        effective_from=effective_from,
        rules=DEFAULT_CAPABILITY_RULES,
    )
