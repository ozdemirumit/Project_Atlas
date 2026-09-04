from __future__ import annotations

import pytest

from atlas.modules.mcp_plugin_sdk.domain.test_categories_fixtures import (
    CapabilityTestCoverageReport,
    CategoryCoverage,
    FailureFixtureKind,
    Fixture,
    RequiredTestCategory,
)


def full_coverage() -> tuple[CategoryCoverage, ...]:
    return tuple(
        CategoryCoverage(
            category=category, covered_scenario_names=(f"{category.value}.happy_path",)
        )
        for category in RequiredTestCategory
    )


def test_test_category_coverage_requires_at_least_one_scenario() -> None:
    with pytest.raises(ValueError, match="at least one covered scenario"):
        CategoryCoverage(category=RequiredTestCategory.UNIT, covered_scenario_names=())


def test_coverage_report_requires_every_category() -> None:
    with pytest.raises(ValueError, match="every required test category"):
        CapabilityTestCoverageReport(
            capability_id="capability.inventory.read",
            coverage=(
                CategoryCoverage(
                    category=RequiredTestCategory.UNIT, covered_scenario_names=("unit.mapping",)
                ),
            ),
        )


def test_coverage_report_accepts_full_coverage() -> None:
    report = CapabilityTestCoverageReport(
        capability_id="capability.inventory.read", coverage=full_coverage()
    )
    assert len(report.coverage) == len(RequiredTestCategory)


def fixture(**overrides: object) -> Fixture:
    defaults: dict[str, object] = {
        "fixture_id": "fixture.inventory-response.example",
        "target_product": "Example Storage",
        "target_version": "6.1",
        "sanitized": True,
        "reviewed": True,
        "capability_schema_version": "schema.output.inventory-read.v1",
        "failure_kind": None,
        "payload": (("volume_count", "42"),),
    }
    defaults.update(overrides)
    return Fixture(**defaults)  # type: ignore[arg-type]


def test_fixture_accepts_valid_state() -> None:
    assert fixture().target_product == "Example Storage"


def test_fixture_requires_sanitization() -> None:
    with pytest.raises(ValueError, match="sanitized and reviewed"):
        fixture(sanitized=False)


def test_fixture_requires_review() -> None:
    with pytest.raises(ValueError, match="sanitized and reviewed"):
        fixture(reviewed=False)


def test_fixture_rejects_secret_looking_payload() -> None:
    with pytest.raises(ValueError, match="no real customer identifiers"):
        fixture(payload=(("api_key", "AKIAABCDEFGHIJKLMNOP"),))


def test_fixture_accepts_failure_kind() -> None:
    result = fixture(failure_kind=FailureFixtureKind.MALFORMED)
    assert result.failure_kind is FailureFixtureKind.MALFORMED
