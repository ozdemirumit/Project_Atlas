"""ATLAS-025 SS24: policy decision audit.

Maps a `PolicyDecision` onto the platform's own `atlas.core.audit.AuditRecord` / `AuditSink` --
the same audit primitive `authorization`'s service already records through -- rather than
building a second, Policy Engine-specific audit path. SS24 requires policy creation/review/
approval/activation/rollback/suspension/retirement, decision request/outcome/reasons/versions,
administrative simulation/export, break-glass use, and decision invalidation to all be audited;
this module covers decision auditing only (what the earlier slices can actually produce), leaving
policy-lifecycle-event and break-glass-use auditing to whatever application service eventually
owns those administrative actions, since this module has no lifecycle/break-glass event of its
own to record yet -- only a `PolicyDecision`.
"""

from __future__ import annotations

from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.policy_engine.domain.models import PolicyDecision, PolicyDecisionOutcome


def _result_code(decision: PolicyDecision) -> str:
    if decision.non_overridable_rule_references:
        return "policy.non_overridable_denied"
    if decision.outcome is PolicyDecisionOutcome.ALLOW:
        return "policy.allowed"
    if decision.outcome is PolicyDecisionOutcome.DENY:
        if decision.reasons and decision.reasons[0].policy_rule_reference is None:
            return "policy.deny_by_default"
        return "policy.rule_denied"
    return "policy.condition_required"


async def record_policy_decision(
    sink: AuditSink,
    decision: PolicyDecision,
    *,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.policy_engine.decision.{decision.outcome.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=decision.decided_at,
            correlation_id=decision.correlation_id,
            subject_id=decision.actor_id,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type=None,
            scope_reference=None,
            decision_id=decision.decision_id,
            outcome=decision.outcome.value,
            result_code=_result_code(decision),
            reason=decision.reasons[0].summary if decision.reasons else None,
        )
    )
