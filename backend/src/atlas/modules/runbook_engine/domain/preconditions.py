"""ATLAS-045 SS11: preconditions.

`is_precondition_evidence_fresh` takes `now` explicitly rather than reading the wall clock,
matching every other freshness check already established in this codebase (e.g.
`PolicySet.is_active_at`, `explainability.models.Explanation.is_stale`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class PreconditionCategory(StrEnum):
    """SS11's eight named categories of preconditions."""

    TARGET_IDENTITY_AND_ENVIRONMENT = "target_identity_and_environment"
    VERSION_COMPATIBILITY = "version_compatibility"
    HEALTH_AND_PROTECTION_STATE = "health_and_protection_state"
    BACKUP_AND_RESTORE_EVIDENCE = "backup_and_restore_evidence"
    READINESS_AND_WINDOW = "readiness_and_window"
    IDENTITY_AND_GOVERNANCE_RECORD = "identity_and_governance_record"
    PLATFORM_HEALTH = "platform_health"
    NO_CONFLICTING_CHANGE = "no_conflicting_change"


class PreconditionFailureBehavior(StrEnum):
    """SS11: "declares whether failure blocks, warns, or routes to an alternative procedure.\""""

    BLOCKS = "blocks"
    WARNS = "warns"
    ROUTES_TO_ALTERNATIVE = "routes_to_alternative"


@dataclass(frozen=True, slots=True)
class RunbookPrecondition:
    """SS11: "each precondition is verifiable, has a freshness limit, and declares [failure
    behavior].\""""

    precondition_id: str
    category: PreconditionCategory
    description: str
    verification_method: str
    freshness_limit_seconds: int
    failure_behavior: PreconditionFailureBehavior
    alternative_procedure_reference: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.precondition_id, "precondition_id")
        if not self.description.strip():
            raise ValueError("a runbook precondition requires a description")
        if not self.verification_method.strip():
            raise ValueError(
                "SS11: each precondition is verifiable -- a verification_method is required"
            )
        if self.freshness_limit_seconds < 1:
            raise ValueError("a runbook precondition requires a positive freshness limit")
        routes_to_alternative = (
            self.failure_behavior is PreconditionFailureBehavior.ROUTES_TO_ALTERNATIVE
        )
        if routes_to_alternative and self.alternative_procedure_reference is None:
            raise ValueError(
                "a precondition that routes to an alternative procedure on failure requires"
                " alternative_procedure_reference"
            )
        if not routes_to_alternative and self.alternative_procedure_reference is not None:
            raise ValueError(
                "alternative_procedure_reference is only meaningful when failure_behavior is"
                " ROUTES_TO_ALTERNATIVE"
            )


def is_precondition_evidence_fresh(
    *, verified_at: datetime, freshness_limit_seconds: int, now: datetime
) -> bool:
    if verified_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("precondition freshness comparison requires timezone-aware datetimes")
    return (now - verified_at).total_seconds() <= freshness_limit_seconds
