from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.runbook_engine.domain.risk_impact import DurationRange
from atlas.modules.runbook_engine.domain.rollback_recovery import (
    RequiredResource,
    RollbackRecoveryKind,
    RunbookRollbackOrRecovery,
    requires_exceptional_governance_for,
)


def entry(**overrides: object) -> RunbookRollbackOrRecovery:
    defaults: dict[str, object] = {
        "reference_id": "runbook-rollback.example",
        "kind": RollbackRecoveryKind.ROLLBACK,
        "forward_step_id": "runbook-step.example",
        "checkpoint_id": "runbook-checkpoint.example",
        "entry_criteria": "The forward step failed before completion.",
        "responsible_role": "role.storage-operator",
        "required_resources": (
            RequiredResource(description="Pre-change configuration backup.", verified=True),
        ),
        "estimated_duration": DurationRange(minimum_minutes=1, maximum_minutes=5),
        "service_effect": "Momentary path interruption during rollback.",
        "has_been_tested": True,
        "is_irreversible": False,
        "partial_execution_recovery_reference": "runbook-recovery.partial-example",
        "unknown_outcome_recovery_reference": "runbook-recovery.unknown-example",
    }
    defaults.update(overrides)
    return RunbookRollbackOrRecovery(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_entry_constructs_cleanly() -> None:
    example = entry()
    assert example.kind is RollbackRecoveryKind.ROLLBACK


def test_required_resource_requires_a_description() -> None:
    with pytest.raises(ValueError, match="description"):
        RequiredResource(description="   ", verified=True)


def test_rejects_blank_entry_criteria() -> None:
    with pytest.raises(ValueError, match="entry criteria"):
        entry(entry_criteria="   ")


def test_rejects_blank_responsible_role() -> None:
    with pytest.raises(ValueError, match="responsible role"):
        entry(responsible_role="   ")


def test_rejects_blank_service_effect() -> None:
    with pytest.raises(ValueError, match="service effect"):
        entry(service_effect="   ")


def test_requires_a_partial_execution_recovery_reference() -> None:
    with pytest.raises(ValueError, match="partial_execution_recovery_reference"):
        entry(partial_execution_recovery_reference="   ")


def test_requires_an_unknown_outcome_recovery_reference() -> None:
    with pytest.raises(ValueError, match="unknown_outcome_recovery_reference"):
        entry(unknown_outcome_recovery_reference="   ")


def test_checkpoint_id_may_be_none() -> None:
    example = entry(checkpoint_id=None)
    assert example.checkpoint_id is None


def test_recovery_kind_constructs_cleanly() -> None:
    example = entry(kind=RollbackRecoveryKind.RECOVERY)
    assert example.kind is RollbackRecoveryKind.RECOVERY


def test_requires_exceptional_governance_for_c5() -> None:
    assert (
        requires_exceptional_governance_for(
            capability_class=CapabilityClass.C5_DESTRUCTIVE, is_irreversible=False
        )
        is True
    )


def test_requires_exceptional_governance_for_irreversible() -> None:
    assert (
        requires_exceptional_governance_for(
            capability_class=CapabilityClass.C3_CONTROLLED_CHANGE, is_irreversible=True
        )
        is True
    )


def test_does_not_require_exceptional_governance_otherwise() -> None:
    assert (
        requires_exceptional_governance_for(
            capability_class=CapabilityClass.C3_CONTROLLED_CHANGE, is_irreversible=False
        )
        is False
    )
