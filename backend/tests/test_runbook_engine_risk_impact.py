from __future__ import annotations

import pytest

from atlas.modules.runbook_engine.domain.risk_impact import (
    DurationRange,
    RunbookRiskImpactDuration,
    effective_duration_range,
)


def duration(**overrides: object) -> DurationRange:
    defaults: dict[str, object] = {"minimum_minutes": 1, "maximum_minutes": 5}
    defaults.update(overrides)
    return DurationRange(**defaults)  # type: ignore[arg-type]


def test_duration_range_rejects_minimum_exceeding_maximum() -> None:
    with pytest.raises(ValueError, match="minimum_minutes must not exceed"):
        duration(minimum_minutes=10, maximum_minutes=5)


def test_duration_range_rejects_negative_minutes() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        duration(minimum_minutes=-1)


def test_duration_range_constructs_cleanly() -> None:
    example = duration()
    assert example.minimum_minutes == 1


def test_effective_duration_range_prefers_target_specific() -> None:
    static = duration(minimum_minutes=1, maximum_minutes=5)
    target_specific = duration(minimum_minutes=10, maximum_minutes=20)
    assert (
        effective_duration_range(static=static, target_specific=target_specific) is target_specific
    )


def test_effective_duration_range_falls_back_to_static_when_none() -> None:
    static = duration(minimum_minutes=1, maximum_minutes=5)
    assert effective_duration_range(static=static, target_specific=None) is static


def declaration(**overrides: object) -> RunbookRiskImpactDuration:
    defaults: dict[str, object] = {
        "runbook_id": "runbook.example",
        "version_id": "runbook-version.example",
        "direct_affected_systems": ("controller-b",),
        "transitive_affected_systems": (),
        "affected_services": ("service.file-shares",),
        "interruption_expected_mode": "none",
        "interruption_range": duration(minimum_minutes=0, maximum_minutes=1),
        "preparation_duration": duration(minimum_minutes=2, maximum_minutes=5),
        "execution_duration": duration(minimum_minutes=1, maximum_minutes=5),
        "stabilization_duration": duration(minimum_minutes=1, maximum_minutes=3),
        "validation_duration": duration(minimum_minutes=1, maximum_minutes=2),
        "rollback_duration": duration(minimum_minutes=1, maximum_minutes=5),
        "recovery_duration": duration(minimum_minutes=1, maximum_minutes=10),
        "redundancy_effect": "Momentary loss of path redundancy during restart.",
        "capacity_effect": "None.",
        "data_effect": "None.",
        "security_effect": "None.",
        "compliance_effect": "None.",
        "worst_credible_outcome": "Failover to controller A with a brief path interruption.",
        "residual_risk": "A concurrent controller A fault would extend the outage.",
        "point_of_no_return_step_id": None,
        "irreversible_step_ids": (),
        "requires_target_specific_impact_analysis": True,
    }
    defaults.update(overrides)
    return RunbookRiskImpactDuration(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_declaration_constructs_cleanly() -> None:
    example = declaration()
    assert example.requires_target_specific_impact_analysis is True


def test_rejects_blank_interruption_expected_mode() -> None:
    with pytest.raises(ValueError, match="expected interruption mode"):
        declaration(interruption_expected_mode="   ")


def test_rejects_blank_worst_credible_outcome() -> None:
    with pytest.raises(ValueError, match="worst credible outcome"):
        declaration(worst_credible_outcome="   ")


def test_rejects_blank_residual_risk() -> None:
    with pytest.raises(ValueError, match="residual risk"):
        declaration(residual_risk="   ")


def test_point_of_no_return_step_id_may_be_none() -> None:
    example = declaration(point_of_no_return_step_id=None)
    assert example.point_of_no_return_step_id is None


def test_point_of_no_return_step_id_must_be_a_stable_identifier() -> None:
    example = declaration(point_of_no_return_step_id="runbook-step.commit")
    assert example.point_of_no_return_step_id == "runbook-step.commit"
