from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256

from atlas.modules.platform.domain.bootstrap_state import BootstrapRunIdentity, BootstrapRunRecord


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
class BootstrapInvalidationImpact:
    changes: tuple[BootstrapInputChange, ...]
    earliest_affected_phase_id: str | None
    reusable_checkpoint_phase_ids: tuple[str, ...]
    invalidated_checkpoint_phase_ids: tuple[str, ...]
    downstream_phase_ids: tuple[str, ...]


def compare_bootstrap_run(
    current: BootstrapRunIdentity,
    candidate: BootstrapRunIdentity,
    record: BootstrapRunRecord,
) -> BootstrapInvalidationImpact:
    changes: list[BootstrapInputChange] = []
    for field, code, boundary in (
        ("release_id", "bootstrap.release.changed", "phase.acquire"),
        ("profile", "bootstrap.profile.changed", "phase.acquire"),
        ("plan_digest", "bootstrap.plan.changed", "phase.acquire"),
        ("resume_key", "bootstrap.resume-key.changed", "phase.acquire"),
        ("configuration_digest", "bootstrap.configuration.changed", "phase.configure"),
    ):
        old = getattr(current, field)
        new = getattr(candidate, field)
        old_value = old.value if hasattr(old, "value") else str(old)
        new_value = new.value if hasattr(new, "value") else str(new)
        if old_value != new_value:
            changes.append(
                BootstrapInputChange(
                    field=field,
                    reason_code=code,
                    old_reference=_safe_reference(field, old_value),
                    new_reference=_safe_reference(field, new_value),
                    earliest_affected_phase_id=boundary,
                )
            )
    if current.phase_ids != candidate.phase_ids:
        mismatch = next(
            (
                index
                for index, pair in enumerate(
                    zip(current.phase_ids, candidate.phase_ids, strict=False)
                )
                if pair[0] != pair[1]
            ),
            min(len(current.phase_ids), len(candidate.phase_ids)),
        )
        boundary_index = min(mismatch, len(current.phase_ids) - 1)
        changes.append(
            BootstrapInputChange(
                field="phase_ids",
                reason_code="bootstrap.phase-order.changed",
                old_reference=_safe_reference("phase_ids", current.phase_ids),
                new_reference=_safe_reference("phase_ids", candidate.phase_ids),
                earliest_affected_phase_id=current.phase_ids[boundary_index],
            )
        )
    phase_positions = {phase_id: index for index, phase_id in enumerate(current.phase_ids)}
    earliest = min(
        (item.earliest_affected_phase_id for item in changes),
        key=lambda item: phase_positions.get(item, 0),
        default=None,
    )
    if earliest is None:
        return BootstrapInvalidationImpact(
            changes=tuple(changes),
            earliest_affected_phase_id=None,
            reusable_checkpoint_phase_ids=record.completed_phase_ids,
            invalidated_checkpoint_phase_ids=(),
            downstream_phase_ids=(),
        )
    boundary_index = phase_positions.get(earliest, 0)
    reusable = tuple(
        item for item in record.completed_phase_ids if phase_positions.get(item, 0) < boundary_index
    )
    return BootstrapInvalidationImpact(
        changes=tuple(changes),
        earliest_affected_phase_id=earliest,
        reusable_checkpoint_phase_ids=reusable,
        invalidated_checkpoint_phase_ids=tuple(
            item for item in record.completed_phase_ids if item not in reusable
        ),
        downstream_phase_ids=current.phase_ids[boundary_index:],
    )


def _safe_reference(field: str, value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return f"sha256:{sha256(field.encode() + b':' + encoded).hexdigest()}"


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
