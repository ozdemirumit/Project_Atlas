"""ATLAS-025 SS21: break-glass emergency procedure.

"Break-glass is not an AI or workflow bypass" -- `BreakGlassRecord` structurally cannot represent
one: it requires a named human identity and a recorded strong-authentication method, so nothing
using it can ever be "autonomous" in the sense SS10's C5_AUTONOMOUS_EXECUTION rule means. That is
exactly why break-glass can override an ordinary policy-set-driven denial but never a
non-overridable one (SS21: "no weakening of C5 autonomous-execution prohibition" -- by the same
principle, of every non-overridable rule, not only that one).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from atlas.core.capabilities import CapabilityClass
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.policy_engine.domain.models import (
    PolicyDecision,
    PolicyDecisionOutcome,
    PolicyReason,
)


@dataclass(frozen=True, slots=True)
class BreakGlassRecord:
    """SS21's requirements as real fields, not a free-text justification blob that could paper
    over a missing one: named human identity, strong authentication, justification, an incident
    or emergency record, a narrow target/capability/duration, and independent notification.
    Post-event review is not modeled here -- it happens after expiry, against this record and the
    decisions it authorized, and belongs to whatever module owns human review workflows."""

    record_id: str
    identity_id: str
    authentication_method: str
    justification: str
    incident_reference: str
    target_id: str
    capability_class: CapabilityClass
    authorized_at: datetime
    duration: timedelta
    notified_identity_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.record_id, "record_id")
        validate_stable_identifier(self.identity_id, "identity_id")
        validate_stable_identifier(self.target_id, "target_id")
        if not self.authentication_method.strip():
            raise ValueError("break-glass requires a recorded authentication method")
        if not self.justification.strip():
            raise ValueError("break-glass requires a justification")
        if not self.incident_reference.strip():
            raise ValueError("break-glass requires an incident or emergency record reference")
        if self.authorized_at.tzinfo is None:
            raise ValueError("authorized_at must be timezone-aware")
        if self.duration.total_seconds() <= 0:
            raise ValueError("break-glass duration must be positive")
        if not self.notified_identity_ids:
            raise ValueError("break-glass requires independent notification")

    @property
    def expires_at(self) -> datetime:
        return self.authorized_at + self.duration

    def is_active_at(self, at: datetime) -> bool:
        return self.authorized_at <= at < self.expires_at


class BreakGlassOverrideError(Exception):
    pass


def apply_break_glass_override(
    decision: PolicyDecision,
    record: BreakGlassRecord,
    *,
    target_id: str,
    capability_class: CapabilityClass,
    now: datetime,
    override_decision_id: str,
) -> PolicyDecision:
    """Break-glass can only ever override a policy-set-driven outcome, never a non-overridable
    denial -- SS10's ten rules are absolute regardless of who is asking, break-glass included.
    Raises if the original decision was denied by the non-overridable minimum, the record does
    not match this exact target and capability class, or the record is not currently active."""
    if decision.non_overridable_rule_references:
        raise BreakGlassOverrideError("break-glass cannot override a non-overridable denial")
    if record.target_id != target_id or record.capability_class is not capability_class:
        raise BreakGlassOverrideError(
            "break-glass record does not match this decision's target or capability class"
        )
    if not record.is_active_at(now):
        raise BreakGlassOverrideError("break-glass record is not currently active")
    return PolicyDecision(
        decision_id=override_decision_id,
        decided_at=now,
        outcome=PolicyDecisionOutcome.ALLOW,
        reasons=(
            PolicyReason(
                summary=(
                    f"Break-glass override {record.record_id} by {record.identity_id}: "
                    f"{record.justification}"
                )
            ),
        ),
        decision_request_id=decision.decision_request_id,
        correlation_id=decision.correlation_id,
        actor_id=decision.actor_id,
        operation_id=decision.operation_id,
        non_overridable_rule_references=(),
        evaluated_policy_set_versions=decision.evaluated_policy_set_versions,
    )
