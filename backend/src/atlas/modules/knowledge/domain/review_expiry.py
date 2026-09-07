"""ATLAS-027 SS23: Review and Expiry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class ReviewDueRecord:
    """SS23: "Internal procedures have review intervals and owners... Overdue content is
    labeled and may be excluded from critical recommendations.\""""

    item_id: str
    item_version: str
    owner: str
    review_interval_days: int
    last_reviewed_at: datetime
    next_review_due_at: datetime

    def __post_init__(self) -> None:
        required = (self.item_id, self.item_version, self.owner)
        if not all(value.strip() for value in required):
            raise ValueError("review due record requires an item, version, and owner")
        if self.review_interval_days < 1:
            raise ValueError("review interval must be positive")
        if self.last_reviewed_at.tzinfo is None or self.next_review_due_at.tzinfo is None:
            raise ValueError("review due timestamps must be timezone-aware")
        if self.next_review_due_at <= self.last_reviewed_at:
            raise ValueError("next review due date must follow the last review")

    def is_overdue_at(self, moment: datetime) -> bool:
        return moment >= self.next_review_due_at


@dataclass(frozen=True, slots=True)
class ProductEndOfSupport:
    """SS23: "Product end-of-support may expire applicable vendor guidance.\""""

    product: str
    version: str
    end_of_support_at: datetime

    def __post_init__(self) -> None:
        if not self.product.strip() or not self.version.strip():
            raise ValueError("end-of-support requires a product and version")
        if self.end_of_support_at.tzinfo is None:
            raise ValueError("end-of-support time must be timezone-aware")

    def expires_guidance_at(self, moment: datetime) -> bool:
        return moment >= self.end_of_support_at


class OwnerAbsenceResolutionKind(StrEnum):
    REASSIGNED = "reassigned"
    SUSPENDED = "suspended"


@dataclass(frozen=True, slots=True)
class OwnerAbsenceResolution:
    """SS23: "Owner absence triggers reassignment or suspension.\""""

    item_id: str
    prior_owner: str
    resolution: OwnerAbsenceResolutionKind
    new_owner: str | None
    resolved_by: str
    resolved_at: datetime
    rationale: str

    def __post_init__(self) -> None:
        required = (self.item_id, self.prior_owner, self.resolved_by, self.rationale)
        if not all(value.strip() for value in required):
            raise ValueError("owner absence resolution requires identity and a rationale")
        if self.resolved_at.tzinfo is None:
            raise ValueError("owner absence resolution time must be timezone-aware")
        if self.resolution is OwnerAbsenceResolutionKind.REASSIGNED:
            if not (self.new_owner is not None and self.new_owner.strip()):
                raise ValueError("a reassignment requires a new owner")
        elif self.new_owner is not None:
            raise ValueError("a suspension cannot carry a new owner")


@dataclass(frozen=True, slots=True)
class ReviewRenewal:
    """SS23: "Bulk renewal without evidence is prohibited." Every renewal -- whether submitted
    one at a time or as part of a batch -- requires its own `evidence_reference`; there is no
    batch-level shortcut that skips it."""

    item_id: str
    item_version: str
    renewed_by: str
    renewed_at: datetime
    evidence_reference: str
    next_review_due_at: datetime

    def __post_init__(self) -> None:
        required = (
            self.item_id,
            self.item_version,
            self.renewed_by,
            self.evidence_reference,
        )
        if not all(value.strip() for value in required):
            raise ValueError("review renewal requires identity and an evidence reference")
        if self.renewed_at.tzinfo is None or self.next_review_due_at.tzinfo is None:
            raise ValueError("review renewal timestamps must be timezone-aware")
        if self.next_review_due_at <= self.renewed_at:
            raise ValueError("a renewal's next review date must follow the renewal itself")


def a_review_renewal_is_recorded_without_an_evidence_reference() -> bool:
    """SS23: "Bulk renewal without evidence is prohibited." `ReviewRenewal` makes an
    evidence-free renewal unconstructable, individually or as part of any batch of them."""
    return False
