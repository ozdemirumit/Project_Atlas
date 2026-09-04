from __future__ import annotations

import pytest

from atlas.modules.runbook_engine.domain.applicability import (
    ApplicabilityFactor,
    ApplicabilityFactorKind,
    ApplicabilityFactorResult,
    ApplicabilityMatch,
)


def factor(**overrides: object) -> ApplicabilityFactor:
    defaults: dict[str, object] = {
        "kind": ApplicabilityFactorKind.VENDOR_AND_VERSION_COMPATIBILITY,
        "result": ApplicabilityFactorResult.EXACT,
        "explanation": "The target's firmware version matches the runbook's tested version.",
    }
    defaults.update(overrides)
    return ApplicabilityFactor(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_factor_constructs_cleanly() -> None:
    example = factor()
    assert example.result is ApplicabilityFactorResult.EXACT


def test_factor_requires_an_explanation() -> None:
    with pytest.raises(ValueError, match="text similarity alone"):
        factor(explanation="   ")


def match(**overrides: object) -> ApplicabilityMatch:
    defaults: dict[str, object] = {
        "runbook_id": "runbook.example",
        "version_id": "runbook-version.example",
        "target_id": "target.example",
        "factors": (factor(),),
    }
    defaults.update(overrides)
    return ApplicabilityMatch(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_match_constructs_cleanly() -> None:
    example = match()
    assert len(example.factors) == 1


def test_match_requires_at_least_one_factor() -> None:
    with pytest.raises(ValueError, match="at least one evaluated factor"):
        match(factors=())


def test_match_rejects_duplicate_factor_kinds() -> None:
    duplicated = (factor(), factor(result=ApplicabilityFactorResult.PARTIAL))
    with pytest.raises(ValueError, match="cannot evaluate the same factor kind twice"):
        match(factors=duplicated)


def test_overall_result_with_all_exact_factors_is_exact() -> None:
    factors = (
        factor(
            kind=ApplicabilityFactorKind.VENDOR_AND_VERSION_COMPATIBILITY,
            result=ApplicabilityFactorResult.EXACT,
        ),
        factor(
            kind=ApplicabilityFactorKind.ENVIRONMENT_AND_TOPOLOGY,
            result=ApplicabilityFactorResult.EXACT,
        ),
    )
    assert match(factors=factors).overall_result is ApplicabilityFactorResult.EXACT


def test_overall_result_is_the_worst_ranked_factor() -> None:
    factors = (
        factor(
            kind=ApplicabilityFactorKind.VENDOR_AND_VERSION_COMPATIBILITY,
            result=ApplicabilityFactorResult.EXACT,
        ),
        factor(
            kind=ApplicabilityFactorKind.CURRENT_STATE, result=ApplicabilityFactorResult.CONFLICTING
        ),
        factor(
            kind=ApplicabilityFactorKind.LIFECYCLE_AND_FRESHNESS,
            result=ApplicabilityFactorResult.COMPATIBLE,
        ),
    )
    assert match(factors=factors).overall_result is ApplicabilityFactorResult.CONFLICTING


def test_a_single_inapplicable_factor_dominates() -> None:
    factors = (
        factor(
            kind=ApplicabilityFactorKind.VENDOR_AND_VERSION_COMPATIBILITY,
            result=ApplicabilityFactorResult.EXACT,
        ),
        factor(
            kind=ApplicabilityFactorKind.ENVIRONMENT_AND_TOPOLOGY,
            result=ApplicabilityFactorResult.INAPPLICABLE,
        ),
    )
    assert match(factors=factors).overall_result is ApplicabilityFactorResult.INAPPLICABLE
