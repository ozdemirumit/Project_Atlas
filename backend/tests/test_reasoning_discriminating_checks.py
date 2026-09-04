from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.reasoning.domain.discriminating_checks import (
    CheckRankingFactors,
    DiscriminatingCheck,
    ExpectedResultUnderHypothesis,
    is_within_capability_ceiling,
    rank_checks,
)


def expected_result(**overrides: object) -> ExpectedResultUnderHypothesis:
    defaults: dict[str, object] = {
        "hypothesis_id": "reasoning-hypothesis.example",
        "expected_result": "Path errors present on fabric A only.",
    }
    defaults.update(overrides)
    return ExpectedResultUnderHypothesis(**defaults)  # type: ignore[arg-type]


def test_expected_result_requires_text() -> None:
    with pytest.raises(ValueError, match="requires text"):
        expected_result(expected_result="   ")


def check(**overrides: object) -> DiscriminatingCheck:
    defaults: dict[str, object] = {
        "check_id": "reasoning-discriminating-check.example",
        "capability_class": CapabilityClass.C1_READ_ONLY,
        "target_id": "target.example",
        "bounded_duration_seconds": 30,
        "bounded_load": "Single read query, negligible load.",
        "bounded_output": "Path status table, under 1KB.",
        "bounded_data_exposure": "No customer data, path metadata only.",
        "expected_results": (
            expected_result(hypothesis_id="reasoning-hypothesis.a"),
            expected_result(hypothesis_id="reasoning-hypothesis.b"),
        ),
        "avoids_service_change": True,
        "stop_condition": "Stop if the query does not return within the timeout.",
        "timeout_seconds": 10,
        "failure_behavior": "Report the query failure as inconclusive, not as evidence.",
    }
    defaults.update(overrides)
    return DiscriminatingCheck(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_check_constructs_cleanly() -> None:
    example = check()
    assert example.avoids_service_change is True


def test_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError, match="bounded_duration_seconds"):
        check(bounded_duration_seconds=0)


def test_rejects_blank_bounded_load() -> None:
    with pytest.raises(ValueError, match="bounded load"):
        check(bounded_load="   ")


def test_requires_at_least_two_expected_results() -> None:
    with pytest.raises(ValueError, match="at least two hypotheses"):
        check(expected_results=(expected_result(),))


def test_rejects_blank_stop_condition() -> None:
    with pytest.raises(ValueError, match="stop condition"):
        check(stop_condition="   ")


def test_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        check(timeout_seconds=0)


def test_rejects_blank_failure_behavior() -> None:
    with pytest.raises(ValueError, match="failure behavior"):
        check(failure_behavior="   ")


def test_is_within_capability_ceiling_true_when_equal() -> None:
    example = check(capability_class=CapabilityClass.C2_DIAGNOSTIC)
    assert (
        is_within_capability_ceiling(check=example, ceiling=CapabilityClass.C2_DIAGNOSTIC) is True
    )


def test_is_within_capability_ceiling_true_when_below() -> None:
    example = check(capability_class=CapabilityClass.C0_INFORMATIONAL)
    assert (
        is_within_capability_ceiling(check=example, ceiling=CapabilityClass.C2_DIAGNOSTIC) is True
    )


def test_is_within_capability_ceiling_false_when_above() -> None:
    example = check(capability_class=CapabilityClass.C3_CONTROLLED_CHANGE)
    assert (
        is_within_capability_ceiling(check=example, ceiling=CapabilityClass.C2_DIAGNOSTIC) is False
    )


def test_check_ranking_factors_rejects_out_of_range_values() -> None:
    with pytest.raises(ValueError, match="must be within"):
        CheckRankingFactors(information_gain=1.5, safety=0.5, freshness=0.5, cost=0.5, time=0.5)


def test_rank_checks_prefers_higher_information_gain() -> None:
    high_gain = check(check_id="reasoning-discriminating-check.high-gain")
    low_gain = check(check_id="reasoning-discriminating-check.low-gain")
    ranked = rank_checks(
        (
            (
                low_gain,
                CheckRankingFactors(
                    information_gain=0.1, safety=0.5, freshness=0.5, cost=0.5, time=0.5
                ),
            ),
            (
                high_gain,
                CheckRankingFactors(
                    information_gain=0.9, safety=0.5, freshness=0.5, cost=0.5, time=0.5
                ),
            ),
        )
    )
    assert ranked[0].check_id == "reasoning-discriminating-check.high-gain"


def test_rank_checks_penalizes_higher_cost_and_time() -> None:
    cheap = check(check_id="reasoning-discriminating-check.cheap")
    expensive = check(check_id="reasoning-discriminating-check.expensive")
    ranked = rank_checks(
        (
            (
                expensive,
                CheckRankingFactors(
                    information_gain=0.5, safety=0.5, freshness=0.5, cost=0.9, time=0.9
                ),
            ),
            (
                cheap,
                CheckRankingFactors(
                    information_gain=0.5, safety=0.5, freshness=0.5, cost=0.1, time=0.1
                ),
            ),
        )
    )
    assert ranked[0].check_id == "reasoning-discriminating-check.cheap"
