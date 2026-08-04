from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class BootstrapInvalidationState(StrEnum):
    EMPTY = "empty"
    UNCHANGED = "unchanged"
    DRIFTED = "drifted"


@dataclass(frozen=True, slots=True)
class BootstrapInputChange:
    field: str
    reason_code: str
    old_reference: str
    new_reference: str
    earliest_affected_phase_id: str


@dataclass(frozen=True, slots=True)
class BootstrapInvalidationPreview:
    preview_id: str
    schema_version: str
    state: BootstrapInvalidationState
    source_run_id: str | None
    source_run_version: int | None
    changes: tuple[BootstrapInputChange, ...]
    earliest_affected_phase_id: str | None
    reusable_checkpoint_phase_ids: tuple[str, ...]
    invalidated_checkpoint_phase_ids: tuple[str, ...]
    downstream_phase_ids: tuple[str, ...]
    remediation: str | None
    generated_at: datetime
    correlation_id: str
    execution_authorized: bool = False
    lease_mutation_authorized: bool = False
    checkpoint_mutation_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
