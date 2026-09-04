from __future__ import annotations

import pytest

from atlas.modules.change_impact.domain.estimation_maturity import (
    DigitalTwinMaturityLevel,
    EstimateProvenance,
    EstimationMethod,
    SimulationOutputRecord,
    permitted_claim_for,
)


def provenance(**overrides: object) -> EstimateProvenance:
    defaults: dict[str, object] = {
        "method": EstimationMethod.APPROVED_RUNBOOK_STEP_TIMING,
        "evidence_references": ("runbook.controller-failover.v3",),
        "has_applicable_support": True,
    }
    defaults.update(overrides)
    return EstimateProvenance(**defaults)  # type: ignore[arg-type]


def test_estimation_method_has_eight_members() -> None:
    assert len(EstimationMethod) == 8


def test_provenance_requires_evidence() -> None:
    with pytest.raises(ValueError, match="at least one evidence reference"):
        provenance(evidence_references=())


def test_provenance_not_insufficient_when_method_is_not_bounded_ai_synthesis() -> None:
    assert provenance().is_insufficient_for_consequential_approval is False


def test_provenance_insufficient_for_ai_synthesis_without_support() -> None:
    result = provenance(method=EstimationMethod.BOUNDED_AI_SYNTHESIS, has_applicable_support=False)
    assert result.is_insufficient_for_consequential_approval is True


def test_provenance_sufficient_for_ai_synthesis_with_support() -> None:
    result = provenance(method=EstimationMethod.BOUNDED_AI_SYNTHESIS, has_applicable_support=True)
    assert result.is_insufficient_for_consequential_approval is False


def test_permitted_claim_for_every_maturity_level() -> None:
    for level in DigitalTwinMaturityLevel:
        assert permitted_claim_for(level)


def test_permitted_claim_for_d0_is_the_weakest_claim() -> None:
    assert "rule-based risk" in permitted_claim_for(DigitalTwinMaturityLevel.D0)


def test_simulation_output_record_requires_model_version() -> None:
    with pytest.raises(ValueError, match="model version"):
        SimulationOutputRecord(
            maturity_level=DigitalTwinMaturityLevel.D1,
            model_version="",
            parameters=(),
            validation_coverage="80% of scenarios",
            known_error="+/- 10%",
        )


def test_simulation_output_record_permitted_claim_matches_level() -> None:
    record = SimulationOutputRecord(
        maturity_level=DigitalTwinMaturityLevel.D2,
        model_version="capacity-model.v2",
        parameters=(("failover_load_factor", "1.3"),),
        validation_coverage="Tested against 40 lab failovers",
        known_error="+/- 5% IOPS",
    )
    assert record.permitted_claim == permitted_claim_for(DigitalTwinMaturityLevel.D2)
