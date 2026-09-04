"""ATLAS-045 SS13: rollback and recovery.

`requires_exceptional_governance_for` is a standalone function rather than a stored field, since
"C5 or irreversible procedures require exceptional governance" depends on the referenced forward
step's `CapabilityClass` (slice 2) as well as this object's own `is_irreversible` flag -- storing
a derived boolean here risks it silently going stale if either input changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.runbook_engine.domain.risk_impact import DurationRange


class RollbackRecoveryKind(StrEnum):
    ROLLBACK = "rollback"
    RECOVERY = "recovery"


@dataclass(frozen=True, slots=True)
class RequiredResource:
    """SS13: "required backups, images, configuration, or spare resources are verified.\""""

    description: str
    verified: bool

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("a required resource needs a description")


@dataclass(frozen=True, slots=True)
class RunbookRollbackOrRecovery:
    """SS13's rollback/recovery contract. `kind is RECOVERY` exists specifically because SS13's
    "recovery is defined when direct rollback is impossible" -- this module does not enforce that
    a RECOVERY entry always has a missing/impossible ROLLBACK counterpart, since whether rollback
    is genuinely impossible is a domain judgment the author makes, not something derivable from
    this object's own fields."""

    reference_id: str
    kind: RollbackRecoveryKind
    forward_step_id: str
    checkpoint_id: str | None
    entry_criteria: str
    responsible_role: str
    required_resources: tuple[RequiredResource, ...]
    estimated_duration: DurationRange
    service_effect: str
    has_been_tested: bool
    is_irreversible: bool
    partial_execution_recovery_reference: str
    unknown_outcome_recovery_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.reference_id, "reference_id")
        validate_stable_identifier(self.forward_step_id, "forward_step_id")
        if self.checkpoint_id is not None:
            validate_stable_identifier(self.checkpoint_id, "checkpoint_id")
        if not self.entry_criteria.strip():
            raise ValueError("a rollback/recovery entry requires entry criteria")
        if not self.responsible_role.strip():
            raise ValueError("a rollback/recovery entry requires a responsible role")
        if not self.service_effect.strip():
            raise ValueError("a rollback/recovery entry requires a service effect statement")
        if not self.partial_execution_recovery_reference.strip():
            raise ValueError(
                "SS13: partial execution has a recovery branch --"
                " partial_execution_recovery_reference is required"
            )
        if not self.unknown_outcome_recovery_reference.strip():
            raise ValueError(
                "SS13: unknown outcomes have a recovery branch --"
                " unknown_outcome_recovery_reference is required"
            )


def requires_exceptional_governance_for(
    *, capability_class: CapabilityClass, is_irreversible: bool
) -> bool:
    """SS13: "C5 or irreversible procedures require exceptional governance outside ordinary
    automation.\""""
    return capability_class is CapabilityClass.C5_DESTRUCTIVE or is_irreversible
