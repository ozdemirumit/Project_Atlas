"""ATLAS-024 SS23/SS24: failure behavior and security/privacy."""

from __future__ import annotations

from enum import StrEnum


class DecisionFailureKind(StrEnum):
    """SS23's eight named failure conditions."""

    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    GRAPH_STALE_OR_INCOMPLETE = "graph_stale_or_incomplete"
    AI_UNAVAILABLE = "ai_unavailable"
    RULE_FAILURE = "rule_failure"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    POLICY_UNAVAILABLE = "policy_unavailable"
    OUTPUT_INVALID = "output_invalid"
    AUDIT_REQUIRED_BUT_UNAVAILABLE = "audit_required_but_unavailable"


class DecisionFailureBehavior(StrEnum):
    """SS23's corresponding required behaviors, one per failure kind."""

    RETURN_INSUFFICIENT_EVIDENCE_AND_NEXT_STEP = "return_insufficient_evidence_and_next_step"
    LIMIT_IMPACT_CLAIM_AND_IDENTIFY_UNKNOWN_BLAST_RADIUS = (
        "limit_impact_claim_and_identify_unknown_blast_radius"
    )
    RETURN_DETERMINISTIC_FINDINGS_DEGRADED = "return_deterministic_findings_degraded"
    EXCLUDE_RULE_AND_DISCLOSE_INCOMPLETE = "exclude_rule_and_disclose_incomplete"
    PRESERVE_CONFLICT_AND_REDUCE_CONFIDENCE = "preserve_conflict_and_reduce_confidence"
    DO_NOT_PRESENT_AS_ALLOWED = "do_not_present_as_allowed"
    BOUNDED_REPAIR_OR_FAIL_WITHOUT_PUBLISHING = "bounded_repair_or_fail_without_publishing"
    FAIL_CLOSED_PER_TASK_POLICY = "fail_closed_per_task_policy"


_REQUIRED_BEHAVIOR_FOR_FAILURE: dict[DecisionFailureKind, DecisionFailureBehavior] = {
    DecisionFailureKind.EVIDENCE_UNAVAILABLE: (
        DecisionFailureBehavior.RETURN_INSUFFICIENT_EVIDENCE_AND_NEXT_STEP
    ),
    DecisionFailureKind.GRAPH_STALE_OR_INCOMPLETE: (
        DecisionFailureBehavior.LIMIT_IMPACT_CLAIM_AND_IDENTIFY_UNKNOWN_BLAST_RADIUS
    ),
    DecisionFailureKind.AI_UNAVAILABLE: (
        DecisionFailureBehavior.RETURN_DETERMINISTIC_FINDINGS_DEGRADED
    ),
    DecisionFailureKind.RULE_FAILURE: (
        DecisionFailureBehavior.EXCLUDE_RULE_AND_DISCLOSE_INCOMPLETE
    ),
    DecisionFailureKind.CONFLICTING_EVIDENCE: (
        DecisionFailureBehavior.PRESERVE_CONFLICT_AND_REDUCE_CONFIDENCE
    ),
    DecisionFailureKind.POLICY_UNAVAILABLE: DecisionFailureBehavior.DO_NOT_PRESENT_AS_ALLOWED,
    DecisionFailureKind.OUTPUT_INVALID: (
        DecisionFailureBehavior.BOUNDED_REPAIR_OR_FAIL_WITHOUT_PUBLISHING
    ),
    DecisionFailureKind.AUDIT_REQUIRED_BUT_UNAVAILABLE: (
        DecisionFailureBehavior.FAIL_CLOSED_PER_TASK_POLICY
    ),
}


def required_behavior_for(failure: DecisionFailureKind) -> DecisionFailureBehavior:
    """SS23's failure-behavior table, exactly as declared."""
    return _REQUIRED_BEHAVIOR_FOR_FAILURE[failure]


class SecurityPrivacyRequirement(StrEnum):
    """SS24's eight named requirements."""

    ACCESS_FILTER_EVIDENCE_BEFORE_ANALYSIS = "access_filter_evidence_before_analysis"
    USE_MINIMUM_NECESSARY_CONTEXT = "use_minimum_necessary_context"
    EXCLUDE_SECRETS_AND_CREDENTIAL_MATERIAL = "exclude_secrets_and_credential_material"
    PREVENT_CROSS_ORGANIZATION_AND_CROSS_ENVIRONMENT_DECISIONS = (
        "prevent_cross_organization_and_cross_environment_decisions"
    )
    TREAT_EVIDENCE_AND_MODEL_OUTPUT_AS_UNTRUSTED = "treat_evidence_and_model_output_as_untrusted"
    RESTRICT_RECORDS_AND_CITATIONS_TO_AUTHORIZED_USERS = (
        "restrict_records_and_citations_to_authorized_users"
    )
    SANITIZE_EXPORTS_AND_AUDIT_METADATA = "sanitize_exports_and_audit_metadata"
    RATE_LIMIT_EXPENSIVE_OR_BROAD_SCOPE_ANALYSIS = "rate_limit_expensive_or_broad_scope_analysis"


def is_cross_organization_or_environment_decision(
    *,
    actor_organization_id: str,
    actor_environment_id: str,
    target_organization_id: str,
    target_environment_id: str,
) -> bool:
    """SS24: "prevent cross-organization and cross-environment decisions." Mirrors Policy
    Engine's `PolicyDecisionRequest.crosses_organization_or_environment_boundary` property for
    Decision Engine's own request shape."""
    return (
        actor_organization_id != target_organization_id
        or actor_environment_id != target_environment_id
    )


def evidence_and_model_output_are_trusted_by_default() -> bool:
    """SS24: "treat evidence and model output as untrusted input." Always `False`."""
    return False
