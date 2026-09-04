"""ATLAS-045 SS4/SS7/SS19: runbook identity, class, lifecycle state, and core version metadata.

Reuses `atlas.core.capabilities.CapabilityClass` for the C0-C5 capability-class ceiling -- the
same type connectors' `CapabilityManifest` already uses -- and
`atlas.core.classification.DataClassification` for data classification, matching every other
governed-content module in this codebase (reports, security_export, knowledge), rather than a
second set of equivalent enums.

SS7 lists roughly thirty metadata elements a runbook version carries. This slice models runbook
identity, ownership/authorship, class, lifecycle state, capability ceiling, classification, and
testing/review/expiry dates -- the elements a later slice does not already own a richer type for.
Compatibility (vendor/product/firmware/connector), organizational applicability, duration/impact/
maintenance-window, and access-policy/retention/export restrictions are deliberately deferred to
the slices that build the "applicability matching" (SS20) and "risk, impact, and duration" (SS12)
contracts, where they get real, checkable types instead of loose strings guessed at here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import validate_stable_identifier


class RunbookClass(StrEnum):
    """SS4's eight runbook classes. Purpose only -- "the class describes purpose, not
    authorization; every step has its own capability class and control requirements" (SS4)."""

    INFORMATIONAL = "informational"
    HEALTH_CHECK = "health_check"
    DIAGNOSTIC = "diagnostic"
    RESTORATION = "restoration"
    MAINTENANCE = "maintenance"
    RECOVERY = "recovery"
    SECURITY_RESPONSE = "security_response"
    VALIDATION = "validation"


_TYPICAL_CAPABILITY_CEILING: dict[RunbookClass, tuple[CapabilityClass, ...]] = {
    RunbookClass.INFORMATIONAL: (CapabilityClass.C0_INFORMATIONAL,),
    RunbookClass.HEALTH_CHECK: (CapabilityClass.C0_INFORMATIONAL, CapabilityClass.C1_READ_ONLY),
    RunbookClass.DIAGNOSTIC: (CapabilityClass.C1_READ_ONLY, CapabilityClass.C2_DIAGNOSTIC),
    RunbookClass.RESTORATION: (
        CapabilityClass.C3_CONTROLLED_CHANGE,
        CapabilityClass.C4_SERVICE_IMPACTING,
    ),
    RunbookClass.MAINTENANCE: (
        CapabilityClass.C3_CONTROLLED_CHANGE,
        CapabilityClass.C4_SERVICE_IMPACTING,
    ),
    RunbookClass.RECOVERY: (
        CapabilityClass.C3_CONTROLLED_CHANGE,
        CapabilityClass.C4_SERVICE_IMPACTING,
        CapabilityClass.C5_DESTRUCTIVE,
    ),
    RunbookClass.SECURITY_RESPONSE: (),
    RunbookClass.VALIDATION: (
        CapabilityClass.C0_INFORMATIONAL,
        CapabilityClass.C1_READ_ONLY,
        CapabilityClass.C2_DIAGNOSTIC,
    ),
}


def typical_capability_ceiling(runbook_class: RunbookClass) -> tuple[CapabilityClass, ...]:
    """SS4's table column, exposed as data. Empty for `SECURITY_RESPONSE`, whose ceiling SS4
    states is "policy-dependent" rather than fixed -- reported honestly rather than guessed."""
    return _TYPICAL_CAPABILITY_CEILING[runbook_class]


class RunbookLifecycleState(StrEnum):
    """SS19's lifecycle diagram states."""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUSPENDED = "suspended"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    RETIRED = "retired"


_ALLOWED_TRANSITIONS: dict[RunbookLifecycleState, frozenset[RunbookLifecycleState]] = {
    RunbookLifecycleState.DRAFT: frozenset({RunbookLifecycleState.REVIEW}),
    RunbookLifecycleState.REVIEW: frozenset(
        {RunbookLifecycleState.DRAFT, RunbookLifecycleState.APPROVED}
    ),
    RunbookLifecycleState.APPROVED: frozenset({RunbookLifecycleState.PUBLISHED}),
    RunbookLifecycleState.PUBLISHED: frozenset(
        {
            RunbookLifecycleState.SUSPENDED,
            RunbookLifecycleState.SUPERSEDED,
            RunbookLifecycleState.EXPIRED,
        }
    ),
    RunbookLifecycleState.SUSPENDED: frozenset(
        {RunbookLifecycleState.PUBLISHED, RunbookLifecycleState.RETIRED}
    ),
    RunbookLifecycleState.SUPERSEDED: frozenset({RunbookLifecycleState.RETIRED}),
    RunbookLifecycleState.EXPIRED: frozenset(
        {RunbookLifecycleState.REVIEW, RunbookLifecycleState.RETIRED}
    ),
    RunbookLifecycleState.RETIRED: frozenset(),
}


def is_allowed_lifecycle_transition(
    *, current: RunbookLifecycleState, target: RunbookLifecycleState
) -> bool:
    """SS19's state diagram, exactly as drawn -- no transition the diagram does not show is
    permitted (including staying in place, which is not a transition)."""
    return target in _ALLOWED_TRANSITIONS[current]


_APPROVAL_REQUIRED_STATES = frozenset(
    {RunbookLifecycleState.APPROVED, RunbookLifecycleState.PUBLISHED}
)


@dataclass(frozen=True, slots=True)
class RunbookVersionMetadata:
    """SS7's core per-version metadata: identity, authorship, class, lifecycle state, capability
    ceiling, classification, and testing/review/expiry dates."""

    runbook_id: str
    version_id: str
    title: str
    purpose: str
    runbook_class: RunbookClass
    owner: str
    steward: str
    authored_by: str
    ai_generated: bool
    reviewers: tuple[str, ...]
    approver: str | None
    state: RunbookLifecycleState
    capability_class_ceiling: CapabilityClass
    classification: DataClassification
    source_reference: str | None
    derived_from_version_id: str | None
    superseded_by_version_id: str | None
    created_at: datetime
    tested_at: datetime | None
    test_environment: str | None
    test_result: str | None
    review_due_at: datetime | None
    expires_at: datetime | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.runbook_id, "runbook_id")
        validate_stable_identifier(self.version_id, "version_id")
        if not self.title.strip():
            raise ValueError("a runbook version requires a title")
        if not self.purpose.strip():
            raise ValueError("a runbook version requires a purpose")
        if not self.owner.strip():
            raise ValueError("a runbook version requires an owner")
        if not self.steward.strip():
            raise ValueError("a runbook version requires a steward")
        if not self.authored_by.strip():
            raise ValueError("a runbook version requires who or what authored it")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        for value, name in (
            (self.tested_at, "tested_at"),
            (self.review_due_at, "review_due_at"),
            (self.expires_at, "expires_at"),
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.state in _APPROVAL_REQUIRED_STATES and self.approver is None:
            raise ValueError(f"a {self.state.value} runbook version requires an approver")
        if self.approver is not None and self.approver == self.authored_by:
            raise ValueError(
                "SS18: the author or generating AI cannot be the sole approver -- approver must"
                " differ from authored_by"
            )
        if self.state is RunbookLifecycleState.SUPERSEDED and self.superseded_by_version_id is None:
            raise ValueError("a superseded runbook version requires the version that superseded it")
