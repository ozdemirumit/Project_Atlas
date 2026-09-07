"""ATLAS-036 SS12: approval synchronization.

ATLAS-037 remains authoritative for the Atlas approval contract; this module models only how an
*external* ITSM approval is admitted as one input to it -- never as a substitute.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ItsmApprovalMappingMode(StrEnum):
    """SS12: "Mappings declare whether ITSM approval is required, informative, or unsupported
    for a given action class.\""""

    REQUIRED = "required"
    INFORMATIVE = "informative"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ItsmExternalApprovalBinding:
    """SS12's four conditions an external approval must satisfy together before Atlas accepts
    it as one input to ATLAS-037's own approval contract."""

    binding_id: str
    profile_id: str
    external_approval_record_id: str
    external_record_version: str
    eligible_approver_reference: str
    approving_subject_reference: str
    exact_plan_reference: str
    exact_plan_version: str
    validated_at: datetime
    atlas_approval_reference: str | None

    def __post_init__(self) -> None:
        for value in (
            self.binding_id,
            self.profile_id,
            self.external_approval_record_id,
            self.external_record_version,
            self.eligible_approver_reference,
            self.approving_subject_reference,
            self.exact_plan_reference,
            self.exact_plan_version,
        ):
            validate_stable_identifier(value, "ITSM external approval binding identifier")
        if self.validated_at.tzinfo is None:
            raise ValueError("an ITSM external approval validation time must be timezone-aware")
        if self.approving_subject_reference != self.eligible_approver_reference:
            raise ValueError("an ITSM external approval binding requires the approver be eligible")
        if self.atlas_approval_reference is not None:
            validate_stable_identifier(
                self.atlas_approval_reference, "ITSM external approval Atlas binding"
            )


def comment_text_or_generic_ticket_state_constitutes_approval() -> bool:
    """SS12: "Comment text, email content, webhook source alone, or a generic ticket state
    cannot be treated as approval.\""""
    return False


class ItsmApprovalInvalidationTrigger(StrEnum):
    """SS12: "Revocation, expiry, rejection, plan change, window change, or approver-scope
    change invalidates dependent execution readiness.\""""

    REVOCATION = "revocation"
    EXPIRY = "expiry"
    REJECTION = "rejection"
    PLAN_CHANGE = "plan_change"
    WINDOW_CHANGE = "window_change"
    APPROVER_SCOPE_CHANGE = "approver_scope_change"


def approval_conflict_allows_consequential_progress() -> bool:
    """SS12: "Conflicts route to human review and stop consequential progress.\""""
    return False
