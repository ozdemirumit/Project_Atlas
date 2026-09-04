from __future__ import annotations

import pytest

from atlas.modules.decision_engine.domain.output_contract import DecisionOutputContract


def output(**overrides: object) -> DecisionOutputContract:
    defaults: dict[str, object] = {
        "problem_or_request_summary": "Why did controller B degrade?",
        "current_assessment": "Fabric instability is the leading candidate cause.",
        "evidence_and_citations": ("evidence.example",),
        "affected_components_and_services": ("service.file-shares",),
        "probable_causes_and_alternatives": ("Resource saturation on controller B.",),
        "confidence_unknowns_assumptions_freshness": (
            "Medium confidence; host queue depth is unknown; evidence collected within 5 minutes."
        ),
        "recommended_steps": ("Query path error counters on both fabrics.",),
        "risk_impact_duration_interruption": (
            "Low risk; momentary redundancy loss; 1-5 minutes; no expected interruption."
        ),
        "preconditions_policy_and_approvals": ("Redundant path confirmed healthy.",),
        "rollback_or_recovery": "Failback to controller A if restart fails.",
        "verification_criteria": ("Controller B reports healthy status.",),
    }
    defaults.update(overrides)
    return DecisionOutputContract(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_output_constructs_cleanly() -> None:
    example = output()
    assert example.rollback_or_recovery is not None


def test_rejects_blank_problem_summary() -> None:
    with pytest.raises(ValueError, match="problem or request summary"):
        output(problem_or_request_summary="   ")


def test_rejects_blank_current_assessment() -> None:
    with pytest.raises(ValueError, match="current assessment"):
        output(current_assessment="   ")


def test_rejects_blank_confidence_section() -> None:
    with pytest.raises(ValueError, match="confidence, unknowns, assumptions"):
        output(confidence_unknowns_assumptions_freshness="   ")


def test_rejects_blank_risk_section() -> None:
    with pytest.raises(ValueError, match="risk, impact, duration"):
        output(risk_impact_duration_interruption="   ")


def test_requires_at_least_one_verification_criterion() -> None:
    with pytest.raises(ValueError, match="verification criterion"):
        output(verification_criteria=())


def test_rollback_or_recovery_may_be_none_when_not_relevant() -> None:
    example = output(rollback_or_recovery=None)
    assert example.rollback_or_recovery is None
