"""ATLAS-025 Policy Engine decision domain contracts.

The decision outcome/reason/request model, plus a pure evaluator for the ten fixed platform
rules ATLAS-025 SS10 calls the "non-overridable minimum" -- the floor every request must clear
before `policy_engine.domain.policy_set` (versioned policy sets) and
`policy_engine.domain.evaluation` (full SS9 precedence combination) are even consulted. Policy is
a control distinct from authentication and RBAC (ATLAS-025 SS4): this module does not decide
whether an actor is authenticated or authorized for a scope, it only refuses to proceed when
upstream context says either one failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.modules.identity.domain.models import validate_stable_identifier


class PolicyDecisionOutcome(StrEnum):
    """The nine outcomes ATLAS-025 SS8 defines. Only ALLOW lets an operation proceed
    unconditionally; every REQUIRE_* outcome is a declared condition, not a partial allow."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_ADDITIONAL_EVIDENCE = "require_additional_evidence"
    REQUIRE_ELEVATED_ROLE = "require_elevated_role"
    REQUIRE_CHANGE_RECORD = "require_change_record"
    REQUIRE_CHANGE_WINDOW = "require_change_window"
    REQUIRE_STEP_UP_AUTHENTICATION = "require_step_up_authentication"
    REQUIRE_MANUAL_EXECUTION = "require_manual_execution"

    @property
    def allowed(self) -> bool:
        return self is PolicyDecisionOutcome.ALLOW


class NonOverridableRule(StrEnum):
    """ATLAS-025 SS10's fixed platform safety minimum. Customer policy may be stricter but
    cannot weaken or remove any of these -- they are evaluated ahead of any versioned policy set
    and cannot be satisfied by an allow rule at any precedence level (SS9)."""

    UNAUTHENTICATED_ACCESS = "unauthenticated_access"
    UNAUTHORIZED_SCOPE = "unauthorized_scope"
    UNKNOWN_CAPABILITY_CLASS = "unknown_capability_class"
    UNTRUSTED_CONNECTOR = "untrusted_connector"
    INVALID_APPROVAL = "invalid_approval"
    SECRET_IN_CONTEXT = "secret_in_context"
    C5_AUTONOMOUS_EXECUTION = "c5_autonomous_execution"
    AI_APPROVAL_OR_EXECUTION = "ai_approval_or_execution"
    AUDIT_UNAVAILABLE = "audit_unavailable"
    CROSS_BOUNDARY_ACCESS = "cross_boundary_access"


class ConnectorTrustState(StrEnum):
    TRUSTED = "trusted"
    DISABLED = "disabled"
    SUSPENDED = "suspended"
    UNTRUSTED = "untrusted"
    INCOMPATIBLE = "incompatible"


class PolicyApprovalStatus(StrEnum):
    """Whether an approval reference on the request is usable. NOT_REQUIRED and NOT_PROVIDED are
    both non-violations of INVALID_APPROVAL -- that rule fires only when an approval was actually
    referenced and found expired or mismatched (SS10, SS12); a genuinely required-but-missing
    approval is a REQUIRE_APPROVAL outcome from a later slice's policy-set evaluation, not a
    non-overridable violation."""

    NOT_REQUIRED = "not_required"
    NOT_PROVIDED = "not_provided"
    VALID = "valid"
    EXPIRED = "expired"
    MISMATCHED = "mismatched"


@dataclass(frozen=True, slots=True)
class PolicyDecisionRequest:
    """The subset of ATLAS-025 SS7's input contract this slice's non-overridable-minimum
    evaluator actually reads. Later slices (policy set resolution, evaluation, evidence
    conditions) extend this contract as they gain fields to consume against a real policy set --
    this is deliberately not the full SS7 shape yet.

    Boolean/enum fields describing actor or context state (is_authenticated,
    is_authorized_for_scope, connector_trust, ...) are never validated as "must be true/valid"
    here: SS7 requires that missing or failing context return deny, not raise, so a request
    describing an unauthenticated, unauthorized, or otherwise failing actor must construct
    cleanly and flow into evaluation.
    """

    decision_request_id: str
    correlation_id: str
    requested_at: datetime
    operation_id: str
    is_authenticated: bool
    is_authorized_for_scope: bool
    actor_id: str
    actor_is_ai: bool
    actor_organization_id: str
    actor_environment_id: str
    target_organization_id: str
    target_environment_id: str
    target_id: str
    capability_class: CapabilityClass | None
    connector_trust: ConnectorTrustState
    approval_status: PolicyApprovalStatus
    context_contains_secret: bool
    operation_is_infrastructure_execution: bool
    operation_is_approval: bool
    execution_is_autonomous: bool
    audit_required: bool
    audit_persistence_available: bool
    cross_boundary_explicitly_permitted: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.decision_request_id, "decision_request_id")
        validate_stable_identifier(self.correlation_id, "correlation_id")
        validate_stable_identifier(self.operation_id, "operation_id")
        validate_stable_identifier(self.actor_id, "actor_id")
        validate_stable_identifier(self.actor_organization_id, "actor_organization_id")
        validate_stable_identifier(self.actor_environment_id, "actor_environment_id")
        validate_stable_identifier(self.target_organization_id, "target_organization_id")
        validate_stable_identifier(self.target_environment_id, "target_environment_id")
        validate_stable_identifier(self.target_id, "target_id")
        if self.requested_at.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware")

    @property
    def crosses_organization_or_environment_boundary(self) -> bool:
        return (
            self.actor_organization_id != self.target_organization_id
            or self.actor_environment_id != self.target_environment_id
        )


@dataclass(frozen=True, slots=True)
class PolicyReason:
    """One entry in a decision's ordered reasons (ATLAS-025 SS8). Exactly one of
    non_overridable_rule or policy_rule_reference is populated for a reason driven by a rule;
    both are None for a deny-by-default reason (no policy rule granted the operation at all --
    ATLAS-025 SS3's "enforce deny-by-default behavior")."""

    summary: str
    non_overridable_rule: NonOverridableRule | None = None
    policy_rule_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("a policy reason requires a summary")
        if self.non_overridable_rule is not None and self.policy_rule_reference is not None:
            raise ValueError(
                "a reason cannot reference both a non-overridable rule and a policy rule"
            )


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """ATLAS-025 SS8's decision record.

    `outcome` is the single most restrictive result (DENY, else the most restrictive matched
    REQUIRE_* outcome by this module's own documented ranking -- SS8 lists nine outcomes but does
    not rank the seven REQUIRE_* variants against each other, so this module picks one:
    REQUIRE_MANUAL_EXECUTION > REQUIRE_STEP_UP_AUTHENTICATION > REQUIRE_CHANGE_WINDOW >
    REQUIRE_CHANGE_RECORD > REQUIRE_ELEVATED_ROLE > REQUIRE_ADDITIONAL_EVIDENCE >
    REQUIRE_APPROVAL, else ALLOW). SS9's "multiple conditions are combined; one satisfied
    condition does not remove another" is honored by `additional_conditions`, which carries every
    other distinct REQUIRE_* outcome that also matched -- nothing is silently dropped just
    because it was not the most restrictive."""

    decision_id: str
    decided_at: datetime
    outcome: PolicyDecisionOutcome
    reasons: tuple[PolicyReason, ...]
    decision_request_id: str
    correlation_id: str
    actor_id: str
    operation_id: str
    non_overridable_rule_references: tuple[NonOverridableRule, ...]
    evaluated_policy_set_versions: tuple[str, ...] = ()
    additional_conditions: tuple[PolicyDecisionOutcome, ...] = ()

    def __post_init__(self) -> None:
        validate_stable_identifier(self.decision_id, "decision_id")
        if self.decided_at.tzinfo is None:
            raise ValueError("decided_at must be timezone-aware")
        if self.outcome is PolicyDecisionOutcome.DENY and not self.reasons:
            raise ValueError("a deny decision requires at least one reason")
        if self.outcome.allowed and self.non_overridable_rule_references:
            raise ValueError("an allow decision cannot carry non-overridable rule references")
        if self.outcome in (PolicyDecisionOutcome.ALLOW, PolicyDecisionOutcome.DENY) and (
            self.additional_conditions
        ):
            raise ValueError("only a REQUIRE_* outcome can carry additional conditions")
        if self.outcome in self.additional_conditions:
            raise ValueError("the primary outcome must not repeat in additional_conditions")
        if len(set(self.additional_conditions)) != len(self.additional_conditions):
            raise ValueError("additional_conditions must not repeat an outcome")


NON_OVERRIDABLE_RULE_SUMMARIES: dict[NonOverridableRule, str] = {
    NonOverridableRule.UNAUTHENTICATED_ACCESS: "The request is not authenticated.",
    NonOverridableRule.UNAUTHORIZED_SCOPE: "The actor is not authorized for the requested scope.",
    NonOverridableRule.UNKNOWN_CAPABILITY_CLASS: (
        "The operation has no recognized capability class."
    ),
    NonOverridableRule.UNTRUSTED_CONNECTOR: (
        "The connector is disabled, suspended, untrusted, or incompatible."
    ),
    NonOverridableRule.INVALID_APPROVAL: "The referenced approval is expired or does not match.",
    NonOverridableRule.SECRET_IN_CONTEXT: "The request context contains a secret value.",
    NonOverridableRule.C5_AUTONOMOUS_EXECUTION: (
        "C5 execution was requested without a human in the loop."
    ),
    NonOverridableRule.AI_APPROVAL_OR_EXECUTION: (
        "An AI actor cannot approve or directly execute infrastructure actions."
    ),
    NonOverridableRule.AUDIT_UNAVAILABLE: (
        "Required audit persistence is unavailable for an audit-required action."
    ),
    NonOverridableRule.CROSS_BOUNDARY_ACCESS: (
        "The request crosses an organization or environment boundary without explicit permission."
    ),
}


def evaluate_non_overridable_minimum(
    request: PolicyDecisionRequest,
) -> tuple[NonOverridableRule, ...]:
    """Pure, deterministic evaluation of ATLAS-025 SS10's ten fixed platform rules against one
    request. Returns every violated rule, in the order SS10 lists them. An empty tuple means the
    request clears the non-overridable floor -- not that it is Allowed outright, since no
    versioned policy set has been evaluated yet (a later slice)."""
    violations: list[NonOverridableRule] = []
    if not request.is_authenticated:
        violations.append(NonOverridableRule.UNAUTHENTICATED_ACCESS)
    if not request.is_authorized_for_scope:
        violations.append(NonOverridableRule.UNAUTHORIZED_SCOPE)
    if request.capability_class is None:
        violations.append(NonOverridableRule.UNKNOWN_CAPABILITY_CLASS)
    if request.connector_trust is not ConnectorTrustState.TRUSTED:
        violations.append(NonOverridableRule.UNTRUSTED_CONNECTOR)
    if request.approval_status in (
        PolicyApprovalStatus.EXPIRED,
        PolicyApprovalStatus.MISMATCHED,
    ):
        violations.append(NonOverridableRule.INVALID_APPROVAL)
    if request.context_contains_secret:
        violations.append(NonOverridableRule.SECRET_IN_CONTEXT)
    if (
        request.capability_class is CapabilityClass.C5_DESTRUCTIVE
        and request.execution_is_autonomous
    ):
        violations.append(NonOverridableRule.C5_AUTONOMOUS_EXECUTION)
    if request.actor_is_ai and (
        request.operation_is_approval or request.operation_is_infrastructure_execution
    ):
        violations.append(NonOverridableRule.AI_APPROVAL_OR_EXECUTION)
    if request.audit_required and not request.audit_persistence_available:
        violations.append(NonOverridableRule.AUDIT_UNAVAILABLE)
    if (
        request.crosses_organization_or_environment_boundary
        and not request.cross_boundary_explicitly_permitted
    ):
        violations.append(NonOverridableRule.CROSS_BOUNDARY_ACCESS)
    return tuple(violations)


def evaluate_policy_decision(
    request: PolicyDecisionRequest,
    *,
    decision_id: str,
    decided_at: datetime,
) -> PolicyDecision:
    """Evaluates only the non-overridable minimum (SS10) -- the floor every request must clear
    before any versioned policy set is even consulted. A clean request resolves to ALLOW *from
    this function alone*, which is correct only when nothing else is meant to run: the full
    evaluator (`policy_engine.domain.evaluation.evaluate_policy`) calls this as its first step,
    then goes on to policy-set evaluation and deny-by-default before producing a real decision --
    use that, not this, wherever a policy set actually exists to evaluate."""
    violations = evaluate_non_overridable_minimum(request)
    if not violations:
        return PolicyDecision(
            decision_id=decision_id,
            decided_at=decided_at,
            outcome=PolicyDecisionOutcome.ALLOW,
            reasons=(),
            decision_request_id=request.decision_request_id,
            correlation_id=request.correlation_id,
            actor_id=request.actor_id,
            operation_id=request.operation_id,
            non_overridable_rule_references=(),
        )
    reasons = tuple(
        PolicyReason(non_overridable_rule=rule, summary=NON_OVERRIDABLE_RULE_SUMMARIES[rule])
        for rule in violations
    )
    return PolicyDecision(
        decision_id=decision_id,
        decided_at=decided_at,
        outcome=PolicyDecisionOutcome.DENY,
        reasons=reasons,
        decision_request_id=request.decision_request_id,
        correlation_id=request.correlation_id,
        actor_id=request.actor_id,
        operation_id=request.operation_id,
        non_overridable_rule_references=violations,
    )
