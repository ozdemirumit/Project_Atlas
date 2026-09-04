from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.decision_engine.domain.findings import (
    AiAssistedAnalysisKind,
    DataQualityState,
    DecisionFinding,
    DeterministicAnalysisKind,
    FindingMethod,
    FindingVersions,
    ai_output_requires_deterministic_validation,
    requires_supporting_evidence,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def test_ai_output_always_requires_deterministic_validation() -> None:
    assert ai_output_requires_deterministic_validation() is True


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        (FindingMethod.OBSERVED, True),
        (FindingMethod.DETERMINISTIC_RULE, True),
        (FindingMethod.CALCULATION, True),
        (FindingMethod.AI_ASSISTED_INFERENCE, False),
    ],
)
def test_requires_supporting_evidence(method: FindingMethod, expected: bool) -> None:
    assert requires_supporting_evidence(method) is expected


def versions(**overrides: object) -> FindingVersions:
    defaults: dict[str, object] = {
        "rule_version": "rule.v1",
        "model_version": None,
        "agent_version": None,
        "prompt_version": None,
        "schema_version": "decision-finding.v1",
    }
    defaults.update(overrides)
    return FindingVersions(**defaults)  # type: ignore[arg-type]


def finding(**overrides: object) -> DecisionFinding:
    defaults: dict[str, object] = {
        "finding_id": "decision-finding.example",
        "finding_type": "capacity_threshold_exceeded",
        "statement": "Controller B's cache utilization exceeded 90% for 10 minutes.",
        "severity": "warning",
        "method": FindingMethod.DETERMINISTIC_RULE,
        "supporting_evidence_ids": ("evidence.example",),
        "contradicting_evidence_ids": (),
        "target_id": "target.example",
        "affected_scope": ("service.file-shares",),
        "first_observed_at": NOW - timedelta(minutes=10),
        "last_observed_at": NOW,
        "data_quality_state": DataQualityState.FRESH,
        "versions": versions(),
        "confidence_basis": "Threshold rule evaluated against ten minutes of telemetry.",
        "unknowns": (),
        "recommended_validation": None,
    }
    defaults.update(overrides)
    return DecisionFinding(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_finding_constructs_cleanly() -> None:
    example = finding()
    assert example.method is FindingMethod.DETERMINISTIC_RULE


def test_rejects_blank_finding_type() -> None:
    with pytest.raises(ValueError, match="finding type"):
        finding(finding_type="   ")


def test_rejects_blank_statement() -> None:
    with pytest.raises(ValueError, match="statement"):
        finding(statement="   ")


def test_rejects_naive_first_observed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        finding(first_observed_at=NOW.replace(tzinfo=None))


def test_rejects_last_observed_before_first_observed() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        finding(first_observed_at=NOW, last_observed_at=NOW - timedelta(minutes=1))


def test_rejects_blank_confidence_basis() -> None:
    with pytest.raises(ValueError, match="confidence basis"):
        finding(confidence_basis="   ")


def test_severity_may_be_none() -> None:
    example = finding(severity=None)
    assert example.severity is None


def test_is_evidence_gap_true_for_evidence_required_method_with_no_evidence() -> None:
    example = finding(method=FindingMethod.OBSERVED, supporting_evidence_ids=())
    assert example.is_evidence_gap is True


def test_is_evidence_gap_false_for_evidence_required_method_with_evidence() -> None:
    example = finding(method=FindingMethod.OBSERVED, supporting_evidence_ids=("evidence.example",))
    assert example.is_evidence_gap is False


def test_is_evidence_gap_false_for_ai_assisted_inference_with_no_evidence() -> None:
    example = finding(method=FindingMethod.AI_ASSISTED_INFERENCE, supporting_evidence_ids=())
    assert example.is_evidence_gap is False


def test_deterministic_analysis_kind_has_seven_members() -> None:
    assert len(DeterministicAnalysisKind) == 7


def test_ai_assisted_analysis_kind_has_six_members() -> None:
    assert len(AiAssistedAnalysisKind) == 6
