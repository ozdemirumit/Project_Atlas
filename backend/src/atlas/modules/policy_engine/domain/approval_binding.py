"""ATLAS-025 SS12: approval binding validation.

Resolves a real `atlas.modules.approvals.domain.models.ApprovalRecord` (the already-governed
human-approval boundary, not a Policy Engine-owned concept) into the `PolicyApprovalStatus` the
non-overridable minimum (SS10) and rule evaluation (SS9) consume. "Any mismatch invalidates
approval" (SS12): this module only ever returns VALID when every check it can perform passes.

SS12 lists seven things approval must match: proposal/plan version, capability/connector version,
exact target/environment, typed-parameter digest, risk/impact references, approver role and
separation of duties, and validity period/change window. `ApprovalPacket`'s real shape (built for
the approvals module's own recommendation-review purpose, not authored against this list) cleanly
supports target, organization, environment, and validity period; it has no connector-version or
typed-parameter-digest field to compare against a policy request today. This module checks what
it genuinely can -- target/organization/environment match, validity period, approval state, and
separation of duties -- and says so plainly rather than silently treating an unchecked dimension
as passing.
"""

from __future__ import annotations

from datetime import datetime

from atlas.modules.approvals.domain.models import ApprovalRecord, ApprovalState
from atlas.modules.policy_engine.domain.models import PolicyApprovalStatus


def validate_approval_binding(
    *,
    target_id: str,
    target_organization_id: str,
    target_environment_id: str,
    requesting_actor_id: str,
    approval: ApprovalRecord | None,
    now: datetime,
) -> PolicyApprovalStatus:
    """SS12's approval-binding check, over what `ApprovalRecord` can actually express today:
    target/organization/environment exact match, the approval not yet expired, no reviewer on
    the approval being the same identity as the requesting actor (separation of duties), and the
    approval record's own state being APPROVED. Any failure short of expiry is MISMATCHED --
    SS12 does not distinguish "wrong target" from "wrong reviewer" as separate outcomes, only
    "any mismatch invalidates approval"."""
    if approval is None:
        return PolicyApprovalStatus.NOT_PROVIDED
    if approval.packet.expires_at <= now or approval.state is ApprovalState.EXPIRED:
        return PolicyApprovalStatus.EXPIRED
    if approval.packet.target_id != target_id:
        return PolicyApprovalStatus.MISMATCHED
    if approval.packet.organization_id != target_organization_id:
        return PolicyApprovalStatus.MISMATCHED
    if approval.packet.environment_id != target_environment_id:
        return PolicyApprovalStatus.MISMATCHED
    if any(decision.reviewer_id == requesting_actor_id for decision in approval.decisions):
        return PolicyApprovalStatus.MISMATCHED
    if approval.state is not ApprovalState.APPROVED:
        return PolicyApprovalStatus.MISMATCHED
    return PolicyApprovalStatus.VALID
